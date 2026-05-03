"""
mining.py — PoW mining + difficulty adjustment

Main functions:
  mine_block(previous_block, transactions, miner_pubkey, difficulty, stop_event)
      -> Block | None   (returns None early when stop_event is set)

  adjust_difficulty(chain, target_interval, current_difficulty)
      -> int            (dynamically adjusts difficulty based on recent block speed)
"""

import threading
import time

from config import DIFFICULTY_BITS, BLOCK_INTERVAL, MINING_REWARD, MAX_NONCE
from blockchain.block import Block
from blockchain.transaction import Transaction


def _meets_difficulty(block_hash: str, bits: int) -> bool:
    prefix = bits // 4
    return block_hash.startswith("0" * prefix)


def mine_block(
    previous_block: Block,
    transactions:   list[Transaction],
    miner_pubkey:   str,
    difficulty:     int = DIFFICULTY_BITS,
    stop_event:     threading.Event | None = None,
) -> Block | None:
    """
    Perform PoW mining over the given set of transactions.

    Args:
        previous_block: The current tail block of the chain
        transactions:   List of transactions to package
        miner_pubkey:   Miner public key (written to block.miner)
        difficulty:     Current difficulty (number of leading zero bits)
        stop_event:     External stop signal; returns None as soon as it is set

    Returns:
        New Block when a valid nonce is found; None if interrupted
    """
    coinbase_tx = Transaction.make_coinbase(miner_pubkey, MINING_REWARD)
    transactions = [coinbase_tx] + list(transactions)

    timestamp = time.time()

    candidate = Block(
        index         = previous_block.index + 1,
        previous_hash = previous_block.hash,
        transactions  = transactions,
        timestamp     = timestamp,
        nonce         = 0,
        miner         = miner_pubkey,
    )

    nonce = 0
    while True:
        if stop_event and stop_event.is_set():
            return None

        candidate.nonce = nonce
        candidate.hash  = candidate.compute_hash()

        if _meets_difficulty(candidate.hash, difficulty):
            return candidate

        nonce += 1
        if nonce > MAX_NONCE:          
            nonce = 0
            candidate.timestamp = time.time()   


def adjust_difficulty(
    block_timestamps: list[float],
    target_interval:  float = BLOCK_INTERVAL,
    current_difficulty: int = DIFFICULTY_BITS,
) -> int:
    """
    Dynamically adjust difficulty based on the average block interval of recent blocks.

    Args:
        block_timestamps:   List of timestamps from recent blocks (at least 2)
        target_interval:    Target block interval (seconds)
        current_difficulty: Current difficulty value

    Returns:
        New difficulty value after adjustment (minimum 1)
    """
    if len(block_timestamps) < 2:
        return current_difficulty

    intervals   = [block_timestamps[i] - block_timestamps[i - 1]
                   for i in range(1, len(block_timestamps))]
    avg_interval = sum(intervals) / len(intervals)

    if avg_interval < target_interval * 0.5:
        return current_difficulty + 1
    elif avg_interval > target_interval * 2.0:
        return max(1, current_difficulty - 1)
    return current_difficulty
