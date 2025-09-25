# 🔮 ReVerify

*"Because trust, but verify... and then reverify... and maybe verify once more just to be sure"*

[![Web3](https://img.shields.io/badge/Web3-Ready-orange.svg)](#)
[![Ethereum](https://img.shields.io/badge/Ethereum-Compatible-purple.svg)](#)

## 🚀 What's This About?

**ReVerify** is your friendly Ethereum contract source code verification wizard! 🧙‍♂️ 

Ever looked at a contract on Etherscan and thought: *"Hmm, this code looks sus... but is it REALLY the code that's deployed?"* Well, now you can find out without losing your mind (or your ETH)!

This tool downloads source code from Etherscan, compiles it with the original settings, and compares the bytecode with what's actually deployed on-chain. 

- 🔍 **Bytecode Verification**: Compares compiled vs deployed bytecode with surgical precision
- 🏗️ **Multi-file Project Support**: Handles complex projects like a boss
- 🔧 **Immutable References**: Deals with those tricky immutable variables that change during deployment
- 📊 **Detailed Analysis**: Shows you exactly where things differ - 🕵️ **Opcode Disassembly**: When you need to go REALLY deep into the bytecode rabbit hole

> Brought to you by mab.xyz with 💜

## 🛠️ Installation

First, make sure you have Python 3.8+ (because we're not animals):

```bash
pip install .
```

Or if you're feeling fancy with a virtual environment (recommended by 9 out of 10 DeFi degens):

```bash
python -m venv reverify-env
source reverify-env/bin/activate  # On Windows: reverify-env\Scripts\activate
pip install .
```

For development installation:

```bash
pip install -e .
```

## 🎯 Usage

### Basic Verification (The "Just Trust Me Bro" Check)

```bash
python reverify.py 0x1234567890123456789012345678901234567890
```

### With Your Own Etherscan API Key (Recommended for Chad Moves)

```bash
python reverify.py 0x1234567890123456789012345678901234567890 --api-key YOUR_API_KEY
```

**Pro Tip**: Set your API key in the keyring to avoid typing it every time:
```python
import keyring
keyring.set_password('login2', "ETHERSCAN_API_TOKEN", "your_api_key_here")
```

## 📝 Example Output

When everything goes right (which is most of the time, unlike your trading strategy):

```
Verifying contract at address: 0xA0b86991c431e59842134d30500e3ee83a67e20e
Downloading contract source code...
Contract Name: FiatTokenV2_1
Compiler Version: v0.6.12+commit.27d51765
Optimization: Yes
Fetching deployed bytecode...
Compiling source code...
Installing and setting solc version: 0.6.12
Processing 2 immutable references
✅ VERIFICATION SUCCESSFUL: Source code matches deployed bytecode
```

When things go sideways (welcome to crypto):

```
❌ VERIFICATION FAILED: Source code does not match deployed bytecode
Compiled bytecode length: 12456
Deployed bytecode length: 12890
First 100 chars of compiled: 608060405234801561001057600080fd5b50600436106101a95760003560e01c8063...
First 100 chars of deployed: 608060405234801561001057600080fd5b50600436106101a95760003560e01c8063...
```

## 🎭 Why This Instead of Sourcify?

Sourcify and Blockscout are the only two known open-source verifier implementations today:
- [Sourcify](https://sourcify.dev/) – [verification](
https://github.com/argotorg/sourcify/blob/staging/packages/lib-sourcify/src/Verification/Verification.ts) through [bytecode transformation](https://github.com/argotorg/sourcify/blob/staging/packages/lib-sourcify/src/Verification/Transformations.ts#L200)
- [Blockscout](https://github.com/blockscout/blockscout) – explorer with [verification in Elixir](https://github.com/blockscout/blockscout/blob/03e4b57557f104c55830d62d3b2905bb603fca44/apps/explorer/lib/explorer/smart_contract/solidity/verifier.ex
)

ReVerify exists to be a third, independent implementation—and the only one in Python. It complements, not replaces, the above:

- Python-native, local-first CLI (no server/DB), easy to script and CI
- Reproduces solc settings from metadata to reverify deployed bytecode
- Detailed bytecode diffs, opcode disassembly, and immutable refs handling
- Great as a second/third opinion to cross-check explorer/registry claims

⚠️ Heads-up: Sourcify covers more edge cases than this tool. If a verification fails here, cross-check it on Sourcify first. If it succeeds there but not here, please open a bug report with contract address and network/chain ID.

Report issues: https://github.com/mab-xyz/mab.xyz-reverify/issues/new

## 🤝 Contributing

Found a bug? Want to add a feature? Think the documentation could use more memes? 

1. Fork this repo
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please make sure your code passes the vibe check ✅

## 🐛 Known Issues & Limitations

- **Vyper contracts**: Not supported yet
- **Ancient Solidity versions**: If you're using Solidity from the Jurassic period, YMMV

## 📄 License

See [LICENSE](LICENSE) file for details.


## 🆘 Support

Having issues? Try these in order:

1. Check if the contract is actually verified on Etherscan
2. Make sure you have a valid Etherscan API key
3. Try turning it off and on again
4. Open an issue with full error logs
5. Send carrier pigeons (not recommended)

---

*Made with ❤️ and an unhealthy amount of coffee by [@mab-xyz](https://github.com/mab-xyz)*

**WAGMI** 🚀🌙

---

### 🎪 Fun Facts

- This tool has verified more contracts than most people have read
- The word "verify" appears 47 times in this README (48 now)
- Immutable references are neither immutable nor references

*Remember: In crypto we trust, but we verify everything else.*