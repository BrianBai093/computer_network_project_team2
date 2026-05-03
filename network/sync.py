"""
sync.py — Startup chain sync + periodic heartbeat

Functions:
  initial_sync(state, tracker_url)  Fetch peers from Tracker on startup and sync the longest chain
  heartbeat_loop(state, tracker_url, self_url, interval)  Background heartbeat thread
"""

import logging
import threading
import time

from config import HEARTBEAT_INTERVAL
from network.peer_client import (fetch_peers, fetch_chain,
                                  register_with_tracker)
from blockchain.block import Block
from blockchain.chain import Chain

log = logging.getLogger(__name__)


def initial_sync(state: dict, tracker_url: str) -> None:
    """
    On startup:
      1. Fetch the peer list from the Tracker
      2. Pull the chain from each peer and replace with the longest valid chain
    """
    peers = fetch_peers(tracker_url)
    state["known_peers"].update(peers)

    best_chain_data: list[dict] | None = None
    best_len = state["chain"].height

    for peer in peers:
        data = fetch_chain(peer)
        if data and len(data) > best_len:
            best_chain_data = data
            best_len        = len(data)

    if best_chain_data:
        try:
            new_chain = Chain.from_list(best_chain_data)
            replaced  = state["chain"].replace_chain(new_chain.get_all_blocks())
            if replaced:
                log.info("initial_sync: replaced chain with length %d", best_len)
        except Exception as e:
            log.warning("initial_sync: failed to replace chain: %s", e)


def heartbeat_loop(state: dict, tracker_url: str,
                   self_url: str, interval: int = HEARTBEAT_INTERVAL) -> None:
    """
    Background thread: send a heartbeat to the Tracker every interval seconds
    and refresh the peer list.
    Controlled by state["stop_event"].
    """
    stop: threading.Event = state.get("stop_event", threading.Event())

    while not stop.is_set():
        try:
            register_with_tracker(tracker_url, self_url)
            peers = fetch_peers(tracker_url)
            if self_url in peers:
                peers.remove(self_url)
            state["known_peers"].update(peers)
        except Exception as e:
            log.debug("heartbeat_loop error: %s", e)

        stop.wait(interval)
