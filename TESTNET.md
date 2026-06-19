# TESTNET.md — Running the Opalyx testnet

Do this **before** mainnet. The testnet uses the same code with a separate
genesis, magic bytes, and ports (P2P 29777 / RPC 29776), so you can break things
freely.

## Prerequisites

1. You built `opalyxd` / `opalyx-cli` (`INSTALL.md` §1–§2).
2. You mined and compiled in the genesis blocks (`INSTALL.md` §3). Without this
   the node asserts on startup with a genesis/merkle mismatch.

## 1. Start a testnet node

```bash
./scripts/start-testnet.sh
```

This launches `opalyxd -testnet` in the foreground with a local-only RPC server
on port 29776, a random RPC password stored in
`~/.opalyx-testnet/.rpccreds`, and `txindex=1` (needed by explorers/miningcore).
Leave it running and open a second terminal for `opalyx-cli`.

Pass extra flags through, e.g. to add a known peer:

```bash
./scripts/start-testnet.sh -addnode=203.0.113.10
```

Control it from another shell (the script prints the exact command, which reads
the saved credentials):

```bash
source ~/.opalyx-testnet/.rpccreds
opalyx-cli -testnet -datadir=$HOME/.opalyx-testnet \
  -rpcuser=$RPCUSER -rpcpassword=$RPCPASS getblockchaininfo
```

For brevity below, assume an alias:

```bash
alias ocli='opalyx-cli -testnet -datadir=$HOME/.opalyx-testnet -rpcuser=$RPCUSER -rpcpassword=$RPCPASS'
```

## 2. Make a wallet address

```bash
ocli getnewaddress
```

(Testnet addresses use the conventional testnet prefixes, not the mainnet `o`
prefix — that is intentional, see `CHAINPARAMS.md`.)

## 3. Mine to your node

KawPow is GPU-mined by an **external** miner; the daemon does not GPU-mine
internally. You have two options on testnet:

**A. Solo via a KawPow miner (real GPU).** Point a KawPow miner (e.g.
`kawpowminer`) at the node's getblocktemplate via a small stratum bridge, or run
a local single-pool Miningcore (see `MINING.md`). Use the testnet pool template
`miningcore/opalyx-pool-template.json` (daemon port already set to 29776).

**B. Quick CPU smoke test on regtest.** If you only want to confirm the chain
advances and transactions work, regtest is far easier because its difficulty is
trivial and `generatetoaddress` works without a GPU:

```bash
opalyxd -regtest -daemon -rpcuser=u -rpcpassword=p -rpcport=39776
opalyx-cli -regtest -rpcuser=u -rpcpassword=p -rpcport=39776 \
  generatetoaddress 101 $(opalyx-cli -regtest -rpcuser=u -rpcpassword=p -rpcport=39776 getnewaddress)
```

After 101 regtest blocks the first coinbase is mature (maturity = 60) and
spendable — a fast end-to-end check of emission, maturity, and the wallet before
you invest in GPU testnet mining.

## 4. Confirm the chain is advancing

```bash
ocli getblockcount
ocli getblockchaininfo | grep -E 'blocks|difficulty|chain'
ocli getmininginfo
```

Difficulty should retarget every block (ASERT), not in 2016-block steps.

## 5. Send a transaction

Once you have a mature balance:

```bash
ocli getbalance
ocli sendtoaddress <some-testnet-address> 1.0
ocli getrawmempool
# mine/await one block, then:
ocli listtransactions
```

## 6. Run a second node and peer them

On another machine (or another datadir/port):

```bash
DATADIR=$HOME/.opalyx-testnet2 ./scripts/start-testnet.sh -port=29787 -addnode=<first-node-ip>
```

Confirm they connect:

```bash
ocli getpeerinfo | grep -E 'addr|subver'
```

Watch both nodes converge on the same `bestblockhash`. That validates P2P magic
bytes, block relay, and consensus agreement across nodes — the core thing the
testnet exists to prove.

## 7. Tear down

Stop with `ocli stop` (or Ctrl-C in the foreground node). To start completely
fresh, delete the datadir:

```bash
rm -rf ~/.opalyx-testnet
```

## Troubleshooting

- **Asserts on startup about genesis/merkle:** you didn't run
  `generate-genesis.sh` and rebuild. Do `INSTALL.md` §3.
- **No peers:** testnet DNS seeds are placeholders until you register them; use
  `-addnode` with a known IP.
- **`getblocktemplate` rejected:** ensure `server=1` and `txindex=1`, and that
  the miner targets the testnet RPC port 29776.
