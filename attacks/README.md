# TrueShot Security Test Suite

Authorized penetration testing tools for the TrueShot blockchain project.

## Attacks

| # | Script | Attack | Severity |
|---|--------|--------|----------|
| 1 | `attack_fake_chain.py` | Forge a longer chain to replace the victim's chain via the sync mechanism | Critical |
| 2 | `attack_tracker_poison.py` | Register a malicious node with the tracker to become a peer of all real nodes | Critical |
| 3 | `attack_tamper_photo.py` | Tamper with a photo and try to get it verified as authentic | High |
| 4 | `attack_flood_mempool.py` | Flood the mempool with garbage transactions to deny service | Medium |
| 5 | `attack_gossip_hijack.py` | Send a crafted block with a malicious sender_url to redirect chain sync | Medium |

## Usage

```bash
# Target = the victim peer node URL (the PC running the project)
# Run each attack from the attacker PC

# Attack 1: Forge and inject a longer chain
python attacks/attack_fake_chain.py --target http://<victim-ip>:8001 --blocks 20

# Attack 2: Poison the tracker
python attacks/attack_tracker_poison.py --tracker http://<victim-ip>:5000 --attacker-url http://<attacker-ip>:9999

# Attack 3: Tamper a photo and verify
python attacks/attack_tamper_photo.py --target http://<victim-ip>:8001 --image photo.jpg

# Attack 4: Flood mempool
python attacks/attack_flood_mempool.py --target http://<victim-ip>:8001 --count 5000

# Attack 5: Gossip hijack
python attacks/attack_gossip_hijack.py --target http://<victim-ip>:8001 --attacker-url http://<attacker-ip>:9999
```
