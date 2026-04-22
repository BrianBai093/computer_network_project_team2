# config.py — Global constants configuration

# ── Blockchain parameters ────────────────────────────────────────────────────
DIFFICULTY_BITS = 4            # PoW initial difficulty (number of leading zero bits)
BLOCK_INTERVAL  = 10           # Target block interval (seconds)
MAX_BLOCK_TXS   = 100          # Maximum transactions per block
GENESIS_HASH    = "0" * 64     # previous_hash for the genesis block

# ── Network parameters ───────────────────────────────────────────────────────
TRACKER_DEFAULT_PORT = 5000
PEER_DEFAULT_PORT    = 8001
HEARTBEAT_INTERVAL   = 30      # Node heartbeat interval (seconds)
GOSSIP_TTL           = 4       # Maximum hops for Gossip messages
SEEN_MSG_CACHE_SIZE  = 1000    # Capacity of the seen-message cache

# ── Application parameters ───────────────────────────────────────────────────
WALLET_FILE        = "wallet.json"
PHASH_THRESHOLD    = 10        # pHash Hamming distance threshold (<=  means similar)
CURVE              = "NIST384p"  # ECDSA curve

# ── Transaction types ────────────────────────────────────────────────────────
TX_REGISTER  = "REGISTER"   # Device registration
TX_CAPTURE   = "CAPTURE"    # Photo capture record
TX_ENDORSE   = "ENDORSE"    # Endorsement
TX_REVOKE    = "REVOKE"     # Revocation
