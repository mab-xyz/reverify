#!/usr/bin/env python3
"""
Ethereum Contract Source Code Verification Script
https://github.com/mab-xyz/reverify
License: AGPL-3.0
"""

import argparse
import json
import os
import requests
import subprocess
import tempfile
import sys
from pathlib import Path
import solcx
import difflib
from evmdasm import EvmBytecode
import cbor2
import re
import hashlib
import base64
import datetime
import keyring
login_keyring=keyring.get_keyring()

class ContractVerifier:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.etherscan.io/v2/api?chainid=1"
        
    def get_contract_source(self, address):
        """Download contract source code from Etherscan, with caching."""
        cache_dir = Path("cache/etherscan_verified")
        cache_file = cache_dir / f"{address}.json"

        if cache_file.exists():
            print(f"Loading contract source for {address} from cache...")
            with open(cache_file, 'r') as f:
                data = json.load(f)
            return data['result'][0]

        params = {
            'module': 'contract',
            'action': 'getsourcecode',
            'address': address,
        }
        
        if self.api_key:
            params['apikey'] = self.api_key
        
        print(f"Downloading contract source for {address} from Etherscan...")
        response = requests.get(self.base_url, params=params)
        response.raise_for_status()
        
        data = response.json()

        if data['status'] != '1':
            raise ValueError(f"API error: {data.get('message', 'Unknown error')}")
            
        result = data['result'][0]
        if not result['SourceCode']:
            raise ValueError("No source code found for this contract")
        
        # Save to cache
        cache_dir.mkdir(parents=True, exist_ok=True)
        with open(cache_file, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Saved contract source for {address} to cache.")
        
        return result
    
    def get_contract_bytecode(self, address):
        """Get deployed bytecode from Etherscan, with caching."""
        cache_dir = Path("cache/etherscan_bytecode")
        cache_file = cache_dir / f"{address}.json"

        if cache_file.exists():
            print(f"Loading bytecode for {address} from cache...")
            with open(cache_file, 'r') as f:
                data = json.load(f)
            return data['result']

        print(f"Fetching bytecode for {address} from Etherscan...")
        bytecode = self._get_contract_bytecode(address)

        # Save to cache
        cache_dir.mkdir(parents=True, exist_ok=True)
        with open(cache_file, 'w') as f:
            json.dump({'result': bytecode}, f, indent=4)
        # print(f"Saved bytecode for {address} to cache.")

        return bytecode
    def _get_contract_bytecode(self, address):
        """Get deployed bytecode from Etherscan"""
        params = {
            'module': 'proxy',
            'action': 'eth_getCode',
            'address': address,
            'tag': 'latest'
        }
        
        if self.api_key:
            params['apikey'] = self.api_key
            
        response = requests.get(self.base_url, params=params)
        response.raise_for_status()
        
        data = response.json()
        return data['result']
    
    def parse_source_code(self, source_data):
        """Parse source code, handling both single files and multi-file projects"""
        source_code = source_data['SourceCode']
        
        if source_code.startswith('{{'):
            # Multi-file project
            source_json_before = json.loads(source_code[1:-1])
            source_json_after = source_json_before
            return source_json_after, source_data
        elif source_code.startswith('{'):
            # Single JSON format
            source_json = json.loads(source_code)
            
            return {"sources":source_json}, source_data
        else:
            # Single file
            contract_name = source_data['ContractName']
            return {"sources":{f"{contract_name}.sol": {"content": source_code}}}, source_data
    
    def compile_standard(self, sources, contract_data):
        """Compile contract using standard JSON input"""
        compiler_version = contract_data['CompilerVersion']
        if "vyper" in compiler_version: 
            raise Exception("vyper support not implemented")
        if compiler_version.startswith('v'):
            compiler_version = compiler_version[1:]
        
        if '+' in compiler_version:
            compiler_version = compiler_version.split('+')[0]
        if '-' in compiler_version:
            compiler_version = compiler_version.split('-')[0]
            
        try:
            print(f"Installing and setting solc version: {compiler_version}")
            solcx.install_solc(compiler_version)
            solcx.set_solc_version(compiler_version, silent=True)
        except Exception as e:
            raise RuntimeError(f"Failed to set solc version {compiler_version}. Error: {e}")

        # Prepare compilation settings
        optimization_used = contract_data.get('OptimizationUsed', '0') == '1'
        optimization_runs = int(contract_data.get('Runs', '200'))
        
        evm_version = contract_data.get('EVMVersion', 'byzantium')
        major, minor, patch = map(int, compiler_version.split('.'))
        
        if evm_version.lower() == 'default':
            if major == 0 and minor >= 8:
                if patch >= 20:
                    evm_version = 'shanghai'
                elif patch >= 18:
                    evm_version = 'paris'
                elif patch >= 13:
                    evm_version = 'london'
                elif patch >= 7:
                    evm_version = 'berlin'
                else:
                    evm_version = 'istanbul'
            elif major == 0 and minor >= 7:
                evm_version = 'istanbul'
            elif major == 0 and minor >= 5 and patch >= 5:
                evm_version = 'petersburg'
            else:
                evm_version = 'byzantium'
        
        # settings = {
        #         "outputSelection": {
        #             "*": {
        #                 "*": ["evm.bytecode", "evm.deployedBytecode", "evm.deployedBytecode.immutableReferences", "metadata"]
        #             }
        #         },
        #         "optimizer": {
        #             "enabled": optimization_used,
        #             "runs": optimization_runs
        #         }
        #     }
        settings={}
        if "settings" in sources:
            settings = sources["settings"]
            # if "viaIR" in settings:
                # return # TODO
            try:
                del settings["optimizer"]["details"]
                # del settings["viaIR"]
            except: pass

        settings["outputSelection"] = {
                    "*": {
                        "*": ["evm.bytecode", "evm.deployedBytecode", "evm.deployedBytecode.immutableReferences", "metadata"]
                    }
                }
        
        if "optimizer" not in settings:
            settings["optimizer"] = {
                    "enabled": optimization_used,
                    "runs": optimization_runs
                }
        # Handle library linking
        if "libraries" in sources and sources["libraries"]:
            print("Adding libraries to compilation settings...")
            settings["libraries"] = sources["libraries"]
        
        # print(sources.keys())
        # Build standard JSON input
        if "sources" not in sources: print(sources)
        standard_json = {
            "language": "Solidity",
            "sources": sources['sources'],
            "settings": settings
        }
        # Add EVM version if supported
        if major > 0 or (major == 0 and minor >= 4 and patch >= 21):
            standard_json["settings"]["evmVersion"] = evm_version
        
        print(standard_json["settings"])
        try:
            print(f"Compiling with standard JSON input...")
            return solcx.compile_standard(standard_json, solc_version=compiler_version)
        except solcx.exceptions.SolcError as e:
            print(f"Compilation failed: {e}")
            raise
    
    def verify_contract(self, address):
        """Main verification function"""

        success_cache_dir = Path("cache/VERIFICATION_SUCCESSFUL")
        success_cache_dir.mkdir(parents=True, exist_ok=True)
        success_file = success_cache_dir / f"{address}.txt"

        if success_file.exists():
            print(f"✅ Contract {address} already verified (cached result)")
            return True

        print(f"Verifying contract at address: {address}")
        
        # Get contract info and source
        print("Downloading contract source code...")
        contract_data = self.get_contract_source(address)
        
        print(f"Contract Name: {contract_data['ContractName']}")
        print(f"Compiler Version: {contract_data['CompilerVersion']}")

        if "vyper" in contract_data['CompilerVersion']:
            print("cannot do vyper")
            return False
        print(f"Optimization: {'Yes' if contract_data.get('OptimizationUsed') == '1' else 'No'}")
        
        # Get deployed bytecode
        print("Fetching deployed bytecode...")
        deployed_bytecode = self.get_contract_bytecode(address)
        
        # Parse and compile source
        sources, _ = self.parse_source_code(contract_data)
        # print(sources)
        print("Compiling source code...")
        compiled_sol = self.compile_standard(sources, contract_data)
        
        # Extract compiled bytecode
        compiled_bytecode, creation_bytecode, immutableReferences = self.extract_bytecode(compiled_sol, contract_data['ContractName'])
        
        # Compare bytecode (remove 0x prefix and compare)
        deployed_clean = deployed_bytecode[2:] if deployed_bytecode.startswith('0x') else deployed_bytecode
        
        # Find CODECOPY and EXTCODECOPY opcodes
        self.find_copy_opcodes(deployed_clean)
    
        constructor_args = contract_data.get('ConstructorArguments', '')
        # print(constructor_args)

        # Map constructor arguments to immutable references
        if constructor_args and immutableReferences:
            print("\nMapping constructor arguments to immutable references...")
            
            # Constructor args are hex-encoded values appended after creation bytecode
            args_hex = constructor_args
            
            # Parse constructor arguments - they are typically 32-byte (64 hex chars) values
            arg_values = []
            for i in range(0, len(args_hex), 64):
                if i + 64 <= len(args_hex):
                    arg_values.append(args_hex[i:i+64])
                else:
                    # Handle last argument if it's shorter
                    arg_values.append(args_hex[i:])
            
            print(f"Found {len(arg_values)} constructor argument values:")
            for i, value in enumerate(arg_values):
                print(f"  Arg {i}: 0x{value}")
            

        # Handle immutable references
        compiled_bytecode = self.handle_immutable_references(compiled_bytecode, immutableReferences, deployed_clean)
        
        # The metadata hash is appended at the end of the deployed bytecode.
        # It's typically 34 bytes long (in hex, 68 chars), starting with a specific sequence.
        # We find the metadata start and truncate it.
        # https://docs.soliditylang.org/en/v0.8.20/metadata.html#encoding-of-the-metadata-hash-in-the-bytecode
        # The pattern is 0xa2 0x64 'i' 'p' 'f' 's' 0x58 0x22 followed by the 32-byte hash
        # In hex: a264697066735822...
        # We can just look for the start of this pattern.
        # A simpler approach that works for solc >= 0.5.9 is to just remove the last 34 bytes.
        # For older versions, it might be different. A common pattern is to find the metadata swarm hash.
        
        # A common way to strip metadata is to find its length from the last two bytes and remove it.
        # The last two bytes of the contract bytecode specify the length of the metadata hash in bytes.
        if len(deployed_clean) > 4:
            try:
                metadata_length_bytes = int(deployed_clean[-4:], 16)
                # total length to remove in hex characters: (metadata_length + 2 bytes for length) * 2
                total_metadata_len_chars = (metadata_length_bytes + 2) * 2
                if len(deployed_clean) >= total_metadata_len_chars:
                    # Extract metadata before removing it
                    metadata_hex = deployed_clean[-total_metadata_len_chars:-4]
                    try:
                        metadata_bytes = bytes.fromhex(metadata_hex)
                        metadata = cbor2.loads(metadata_bytes)
                        print(f"Deployed contract metadata: {metadata}")
                    except Exception as e:
                        print(f"Failed to parse deployed metadata as CBOR: {e}")
                    
                    deployed_clean = deployed_clean[:-total_metadata_len_chars]
            except ValueError:
                # If the end is not a valid hex for length, we assume no metadata or an unknown format.
                pass

        if compiled_bytecode and len(compiled_bytecode) > 4:
            try:
                metadata_length_bytes = int(compiled_bytecode[-4:], 16)
                total_metadata_len_chars = (metadata_length_bytes + 2) * 2
                if len(compiled_bytecode) >= total_metadata_len_chars:
                    # Extract metadata before removing it
                    metadata_hex = compiled_bytecode[-total_metadata_len_chars:-4]
                    try:
                        metadata_bytes = bytes.fromhex(metadata_hex)
                        metadata = cbor2.loads(metadata_bytes)
                        print(f"Compiled contract metadata: {metadata}")
                    except Exception as e:
                        print(f"Failed to parse compiled metadata as CBOR: {e}")
                    
                    compiled_bytecode = compiled_bytecode[:-total_metadata_len_chars]
            except (ValueError, TypeError):
                pass

        # The constructor arguments are appended to the compiled bytecode during deployment.
        # We need to find where the runtime bytecode ends and the constructor arguments begin.
        # The compiled bytecode from solc is just the runtime part.
        # The deployed code is runtime + constructor args (if any) + metadata.
        # After stripping metadata, we should have runtime + constructor args.
        # So, the deployed code should START WITH the compiled code.
        
        # The compiled bytecode from solc is the runtime bytecode.
        # The deployed code on-chain is also the runtime bytecode.
        # However, sometimes there are slight differences or extra data.
        # A common verification method is to check if the compiled bytecode
        # is a prefix of the deployed bytecode (after metadata stripping).
        
        # If there are constructor arguments provided by Etherscan, we can
        # be more certain by checking if the rest of the deployed code
        # matches these arguments.
        if constructor_args:
            remaining_code = deployed_clean[len(compiled_bytecode):]
            if remaining_code == constructor_args:
                print("✅ constructor arguments match.")

            else:
                # It's possible the constructor args on Etherscan are wrong, but bytecode is right.
                # We can still consider it a match if the remaining code is empty or just padding.
                if not remaining_code.strip('0'):
                        print("Note: remaining data is zero padding.")
                        # return True
                
                print("Bytecode matches, but constructor arguments do not.")
                print(f"Etherscan Constructor Arguments: {constructor_args}")
                print(f"Remaining Deployed Code:         {remaining_code}")
                # Continue to the final check, which might still pass.
        else:
            # No constructor args on Etherscan. If the rest is empty/padding, it's a match.
            remaining_code = deployed_clean[len(compiled_bytecode):]
            if not remaining_code.strip('0'):
                print("no constructor arguments found.")

        # Fallback to the original substring check, which is more lenient.
        # Deployed bytecode can contain constructor arguments and metadata.
        # We check if the compiled bytecode is a substring of the deployed one.
        if compiled_bytecode and compiled_bytecode in deployed_clean:
            print("✅ VERIFICATION SUCCESSFUL: Source code matches deployed bytecode")
            # Log success to cache
            with open(success_file, 'w') as f:
                f.write(f"Verification successful at {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n")
                f.write(f"Contract: {contract_data['ContractName']}\n")
                f.write(f"Compiler: {contract_data['CompilerVersion']}\n")
            
            return True
        else:
            print("❌ VERIFICATION FAILED: Source code does not match deployed bytecode")
            print(f"Compiled bytecode length: {len(compiled_bytecode)}")
            print(f"Deployed bytecode length: {len(deployed_clean)}")
            
            if compiled_bytecode:
                print(f"First 100 chars of compiled: {compiled_bytecode[:200]}")
            print(f"First 100 chars of deployed: {deployed_clean[:200]}")
            print("\nDisassembling bytecode for comparison...")
            try:
                compiled_opcodes = EvmBytecode(bytes.fromhex(compiled_bytecode)).disassemble()
                compiled_disassembly = [f"{op.name} {op.operand if op.operand else ''}" for op in compiled_opcodes]

                deployed_opcodes = EvmBytecode(bytes.fromhex(deployed_clean)).disassemble()
                deployed_disassembly = [f"{op.name} {op.operand if op.operand else ''}" for op in deployed_opcodes]

                diff = difflib.unified_diff(
                    compiled_disassembly,
                    deployed_disassembly,
                    fromfile='compiled_disassembly',
                    tofile='deployed_disassembly',
                    lineterm='',
                )
                print("\n--- Opcode Diff ---")
                print('\n'.join(diff))
            except Exception as e:
                print(f"\nCould not generate opcode diff: {e}")

            return False


    
    def handle_immutable_references(self, compiled_bytecode, immutable_references, deployed_bytecode):
        """Handle immutable references by replacing placeholders with actual values from deployed code"""
        if not compiled_bytecode or not immutable_references:
            return compiled_bytecode
            
        print(f"Processing {len(immutable_references)} immutable references")
        result_bytecode = compiled_bytecode
        
        # immutable_references is a dict where keys are immutable variable IDs
        # and values are arrays of byte positions where they appear
        for var_id, positions in immutable_references.items():
            print(f"Processing immutable variable {var_id} at {len(positions)} positions")
            
            for pos_info in positions:
                # pos_info should contain 'start' and 'length'
                start_pos = pos_info['start'] * 2  # Convert to hex position
                length = pos_info['length'] * 2    # Convert to hex length
                
                # Extract the value from deployed bytecode at this position
                if start_pos + length <= len(deployed_bytecode):
                    deployed_value = deployed_bytecode[start_pos:start_pos + length]
                    
                    # Replace in compiled bytecode
                    # print(f"Replacing immutable {var_id} at position {start_pos//2} with {deployed_value}")
                    result_bytecode = (result_bytecode[:start_pos] + 
                                     deployed_value + 
                                     result_bytecode[start_pos + length:])
                else:
                    print(f"Warning: immutable reference position {start_pos//2} exceeds deployed bytecode length")
        
        return result_bytecode
    
    def submit_build_attestation(self, contract_address, contract_data, compiled_bytecode, deployed_bytecode):
        # not yet implemented
        pass
    
    def find_copy_opcodes(self, bytecode):
        """Find CODECOPY (0x39) and EXTCODECOPY (0x3c) opcodes in bytecode"""
        print("\n--- Searching for CODECOPY and EXTCODECOPY opcodes ---")
        
        # CODECOPY = 0x39, EXTCODECOPY = 0x3c
        codecopy_opcode = '39'
        extcodecopy_opcode = '3c'
        
        codecopy_positions = []
        extcodecopy_positions = []
        
        # Search for opcodes (each byte is 2 hex chars)
        for i in range(0, len(bytecode) - 1, 2):
            byte_val = bytecode[i:i+2]
            if byte_val == codecopy_opcode:
                codecopy_positions.append(i // 2)  # Convert to byte position
            elif byte_val == extcodecopy_opcode:
                extcodecopy_positions.append(i // 2)
        
        if codecopy_positions:
            print(f"Found CODECOPY (0x39) at byte positions: {len(codecopy_positions)}")
            for pos in codecopy_positions[:5]:  # Show first 5
                hex_pos = pos * 2
                context = bytecode[max(0, hex_pos-20):hex_pos+30]  # Show context
                print(f"  Position {pos}: ...{context}...")
        else:
            print("No CODECOPY opcodes found")
            
        # if extcodecopy_positions:
        #     print(f"Found EXTCODECOPY (0x3c) at byte positions: {len(extcodecopy_positions)}")
        #     for pos in extcodecopy_positions[:5]:  # Show first 5
        #         hex_pos = pos * 2
        #         context = bytecode[max(0, hex_pos-20):hex_pos+30]  # Show context
        #         print(f"  Position {pos}: ...{context}...")
        # else:
        #     print("No EXTCODECOPY opcodes found")
            
        print("--- End opcode search ---\n")
    
    def extract_bytecode(self, solc_output, contract_name):
        """Extract bytecode from standard JSON compilation output"""
        contracts = solc_output.get('contracts', {})
        
        for file_name, file_contracts in contracts.items():
            if contract_name in file_contracts:

                contract_info = file_contracts[contract_name]
                # print(contract_info)
                # Extract bytecode from standard JSON format
                deployed_bytecode = contract_info.get('evm', {}).get('deployedBytecode', {}).get('object', '')
                creation_bytecode = contract_info.get('evm', {}).get('bytecode', {}).get('object', '')
                immutableReferences = contract_info.get('evm', {}).get('deployedBytecode', {}).get('immutableReferences', '')
                
                return deployed_bytecode, creation_bytecode, immutableReferences
        
        return None, None, None 


def main():
    parser = argparse.ArgumentParser(description='Verify Ethereum contract source code')
    parser.add_argument('address', help='Contract address to verify')
    parser.add_argument('--api-key', help='Etherscan API key (or set ETHERSCAN_API_KEY env var)', default=login_keyring.get_password('login2', "ETHERSCAN_API_TOKEN"))
    
    args = parser.parse_args()
    
    verifier = ContractVerifier(api_key=args.api_key)
    success = verifier.verify_contract(args.address)
    sys.exit(0 if success else 1)
        


if __name__ == '__main__':
    main()
