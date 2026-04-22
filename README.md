# TrueShot — P2P 区块链照片认证系统

基于 P2P 网络和区块链的照片真实性认证系统。每张照片通过密码学手段绑定到已注册设备，并以不可篡改的方式记录在账本上。

---

## 快速启动

```bash
# 安装依赖
pip install flask ecdsa Pillow ImageHash requests pytest

# 终端 1 — 启动 Tracker
python run_tracker.py

# 终端 2 — 启动 Peer 节点
python run_peer.py --tracker-url http://localhost:5000 --web-port 8001

# 浏览器访问
open http://localhost:8001
```

运行测试：
```bash
python -m pytest tests/ -v
```

---

## 已完成的工作

### 项目基础架构
- [x] 完整目录结构（所有包和文件已创建）
- [x] `config.py` — 全局常量（难度、端口、阈值、交易类型）
- [x] `requirements.txt`

### 第一层 — 区块链核心（`blockchain/`）
- [x] `transaction.py` — `Transaction` 数据类；`to_dict` / `from_dict` 序列化；`signable_bytes`；四种工厂方法（`make_register`、`make_capture`、`make_endorse`、`make_revoke`）
- [x] `merkle.py` — Merkle 根计算（处理奇数节点和空列表）
- [x] `block.py` — `Block` 数据类；`compute_hash`；`to_dict` / `from_dict`
- [x] `chain.py` — `Chain` 类（含创世块）；`is_valid_new_block`；`is_valid_chain`；`append_block`；`replace_chain`（最长链规则）；完整序列化；线程安全
- [x] `mempool.py` — `Mempool` 类；`add`（按 tx_id 去重）；`get_pending`；`remove`；线程安全
- [x] `mining.py` — `mine_block`（PoW 循环，支持 `stop_event` 中断）；`adjust_difficulty`（根据平均出块间隔动态调整）

### 第二层 — P2P 网络（`network/`）
- [x] `gossip.py` — `SeenMessages` LRU 缓存，防止消息重复转发
- [x] `tracker.py` — Flask Tracker 服务器（`/register`、`/peers`、`/health`，含超时剪枝）
- [x] `peer_server.py` — Flask Blueprint（`/api/blocks`、`/api/peers`、`/api/transaction`、`/api/block`、`/api/health`）
- [x] `peer_client.py` — `broadcast_transaction`、`broadcast_block`、`fetch_chain`、`fetch_peers`、`register_with_tracker`
- [x] `sync.py` — `initial_sync`（启动时同步最长链）；`heartbeat_loop`（后台心跳线程）

### 第三层 — 应用逻辑（`application/`）
- [x] `crypto_utils.py` — `generate_keypair`、`sign`、`verify`（ECDSA / NIST384p）、`pubkey_to_device_id`
- [x] `image_utils.py` — `sha256_file/bytes`、`phash_file/bytes`、`phash_distance`、`is_similar`
- [x] `wallet.py` — `Wallet` 类；`generate`、`from_file`、`save`
- [x] `device.py` — `register_device`、`is_device_registered`、`is_device_revoked`
- [x] `capture.py` — `record_capture`（计算哈希并创建 CAPTURE 交易）
- [x] `endorse.py` — `endorse_capture`、`get_endorsements`
- [x] `verify.py` — `verify_image`（三态验证：AUTHENTIC / SUSPICIOUS / UNKNOWN）

### 第四层 — Web UI（`web/`）
- [x] `app.py` — Flask 工厂函数
- [x] `routes.py` — 六个页面全部接通（首页、注册、拍照、验证、背书、区块浏览器）
- [x] 七个 HTML 模板（基础布局 + 五个功能页 + 区块浏览器）
- [x] `static/style.css` — 基础样式
- [x] `static/app.js` — 文件上传辅助

### 启动入口
- [x] `run_tracker.py` — 可直接运行，支持 `--port`
- [x] `run_peer.py` — 可直接运行，支持 `--tracker-url`、`--web-port`、`--wallet-file`、`--no-mine`

### 测试骨架
- [x] `tests/test_blockchain.py` — 区块链层单元测试（部分已通过，部分为 TODO 占位）
- [x] `tests/test_network.py` — Tracker 和 SeenMessages 测试通过；Peer API 占位待填
- [x] `tests/test_application.py` — 加密和钱包测试通过；工作流测试占位待填
- [x] `tests/test_web.py` — Flask 页面测试通过；图片上传测试占位待填

> **当前测试状态：64 个测试全部通过（`python -m pytest tests/ -v`）**

---

## 待完成的工作

### 成员 A — 区块链层（`blockchain/`）
- [ ] **交易签名验证**：`chain.py` 的 `append_block` 目前不校验每笔交易的 `signature` 字段，需要在区块入链时验证所有交易签名
- [ ] **REVOKE 权限校验**：目前任何人都可以提交针对任意设备的 REVOKE 交易，需限制为只有设备所有者（同一公钥）才能吊销自己的设备
- [ ] **Coinbase 交易**（可选）：若规范要求矿工奖励，需实现区块奖励机制
- [ ] 补全 `test_blockchain.py` 中的 TODO 测试（有效区块追加、链替换、无效区块拒绝）

### 成员 B — 网络层（`network/`）
- [ ] **Gossip 扇出控制**：目前广播到所有已知节点，应改为随机选取 3–5 个节点转发，避免网络风暴
- [ ] **分叉冲突同步**：`append_block` 失败（检测到分叉）时，应自动触发向发送方拉取完整链并执行 `replace_chain`
- [ ] **节点间 Peer 列表共享**：节点之间应互相交换已知节点列表，而不只依赖 Tracker
- [ ] **接收交易时验证签名**：`/api/transaction` 目前直接将收到的交易加入 mempool，未验证 ECDSA 签名
- [ ] 补全 `test_network.py` 中的 TODO 测试（mock HTTP、广播逻辑验证）

### 成员 C — 应用层（`application/`）
- [ ] **verify_image 签名复验**：`verify_image` 目前只检查设备注册状态，未对链上 CAPTURE 交易的 ECDSA 签名做二次验证
- [ ] **重复拍照检测**：`record_capture` 应检测同一 `image_hash` 是否已上链，避免重复记录
- [ ] **防止自我背书**：`endorse_capture` 应拒绝 `endorser_device_id == capture.device_id` 的情况
- [ ] 补全 `test_application.py` 中的 pHash 图片测试（需构造内存中的 PIL 图片）
- [ ] 补全端到端工作流测试（注册→挖矿→拍照→挖矿→验证→背书→吊销）

### 成员 D — Web + 集成（`web/`、`tests/`、`run_peer.py`）
- [ ] **图片上传测试**：`test_post_capture_with_image` 和 `test_post_verify_unknown_image` 需要真实的内存 PNG fixture
- [ ] **区块浏览器时间格式**：时间戳目前显示为原始 Unix 浮点数，应格式化为可读日期时间
- [ ] **区块浏览器分页**：链条过长时页面会溢出，需实现分页
- [ ] **自定义错误页面**：缺少 404 / 500 错误模板
- [ ] **Demo 脚本**：编写一个脚本，自动启动 1 个 Tracker + 3 个 Peer，注册设备、记录照片、背书、并打印验证结果
- [ ] **优雅关闭**：`run_peer.py` 的 `stop_event` 尚未绑定 SIGINT/SIGTERM 信号
- [ ] 补全 `test_web.py` 中所有剩余的 TODO 测试

---

## 剩余工作分工

| 成员 | 负责模块 | 核心待办事项 |
|------|----------|------------|
| **A — 区块链** | `blockchain/` | 入链时验证交易签名；REVOKE 权限校验；补全单元测试 |
| **B — 网络** | `network/` | Gossip 扇出（随机子集）；分叉触发链同步；节点列表共享；接收交易验签；网络测试 |
| **C — 应用** | `application/` | verify_image 签名复验；重复拍照检测；自我背书防护；pHash 测试；端到端工作流测试 |
| **D — Web+集成** | `web/`, `tests/`, `run_peer.py` | 图片上传测试；时间格式化；Demo 脚本；优雅关闭；补全 Web 测试 |

---

## 系统架构

```
run_tracker.py                    run_peer.py
      |                                 |
network/tracker.py            web/app.py (Flask)
                               ├── network/peer_server.py   (/api/*)
                               └── web/routes.py            (/* UI)
                                       |
                            ┌──────────┴──────────┐
                     blockchain/             application/
                     chain.py                verify.py
                     mempool.py              capture.py
                     mining.py               device.py
                     block.py                endorse.py
                     transaction.py          wallet.py
                     merkle.py               crypto_utils.py
                                             image_utils.py
```

---

## 交易类型说明

| 类型 | 发起方 | 关键 payload 字段 |
|------|--------|------------------|
| `REGISTER` | 设备所有者 | `device_id`、`public_key`、`metadata` |
| `CAPTURE` | 已注册设备 | `device_id`、`image_hash`（SHA-256）、`phash`、`location` |
| `ENDORSE` | 任意已注册设备 | `target_tx_id`、`endorser_device_id` |
| `REVOKE` | 设备所有者 | `target_device_id`、`reason` |

## 验证结果说明

| 结果 | 含义 |
|------|------|
| `AUTHENTIC` | 链上存在精确 SHA-256 匹配；设备已注册且未被吊销 |
| `SUSPICIOUS` | 链上存在感知相似图片（pHash 汉明距离 ≤ 阈值）但哈希不同——可能被后期处理 |
| `UNKNOWN` | 链上未找到任何匹配或相似记录 |
