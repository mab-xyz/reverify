import unittest
from unittest.mock import MagicMock, patch
import json
import sys
import os

# Add project root to sys.path so we can import reverify
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from reverify import ContractVerifier

class TestContractVerifier(unittest.TestCase):
    def setUp(self):
        self.verifier = ContractVerifier(api_key="test_key")

    @patch('reverify.requests.get')
    @patch('reverify.solcx.install_solc')
    @patch('reverify.solcx.set_solc_version')
    @patch('reverify.solcx.compile_standard')
    def test_verify_contract_success(self, mock_compile, mock_set_version, mock_install, mock_get):
        # Mock Etherscan responses
        address = "0x1234567890123456789012345678901234567890"
        
        # Mock get_contract_source response
        source_response = MagicMock()
        source_response.json.return_value = {
            "status": "1",
            "result": [{
                "SourceCode": "contract Test { }",
                "ContractName": "Test",
                "CompilerVersion": "v0.8.0+commit.c7dfd78e",
                "OptimizationUsed": "1",
                "Runs": "200",
                "ConstructorArguments": ""
            }]
        }
        
        # Mock get_contract_bytecode response
        # Note: get_contract_bytecode calls _get_contract_bytecode which calls requests.get
        bytecode_response = MagicMock()
        bytecode_response.json.return_value = {
            "result": "0x6080604052348015600f57600080fd5b50603f80601d6000396000f3fe6080604052600080fdfea2646970667358221220dceca8706b29e917d2358f278d6f966d54639965254247559c551d740c88316364736f6c63430008000033"
        }

        # Configure mock_get side effects
        def get_side_effect(*args, **kwargs):
            if kwargs.get('params', {}).get('action') == 'getsourcecode':
                return source_response
            elif kwargs.get('params', {}).get('action') == 'eth_getCode':
                return bytecode_response
            return MagicMock()
            
        mock_get.side_effect = get_side_effect

        # Mock compile_standard response
        # The compiled bytecode should match the deployed bytecode (runtime part)
        # For simplicity, let's make them match exactly in the mock, excluding metadata if possible
        # In the code: deployed_clean = deployed_bytecode[2:]
        # The code checks: if compiled_bytecode in deployed_clean
        
        # This is a dummy bytecode that matches the start of the "deployed" one above (minus metadata)
        dummy_bytecode = "6080604052600080fdfe" 
        
        mock_compile.return_value = {
            "contracts": {
                "Test.sol": {
                    "Test": {
                        "evm": {
                            "deployedBytecode": {
                                "object": dummy_bytecode,
                                "immutableReferences": {}
                            },
                            "bytecode": {
                                "object": "6080604052348015600f57600080fd5b50603f80601d6000396000f3fe" + dummy_bytecode
                            }
                        }
                    }
                }
            }
        }

        # Run verification
        # We need to mock the cache check to avoid file I/O or existing cache
        with patch('pathlib.Path.exists', return_value=False), \
             patch('pathlib.Path.mkdir'), \
             patch('builtins.open', new_callable=MagicMock):
            
            result = self.verifier.verify_contract(address)
            
        self.assertTrue(result)
        mock_install.assert_called_with("0.8.0")

    def test_parse_source_code_single_file(self):
        source_data = {
            "SourceCode": "contract Test {}",
            "ContractName": "Test"
        }
        sources, _ = self.verifier.parse_source_code(source_data)
        self.assertIn("Test.sol", sources["sources"])
        self.assertEqual(sources["sources"]["Test.sol"]["content"], "contract Test {}")

    def test_parse_source_code_json(self):
        source_data = {
            "SourceCode": "{\"A.sol\": {\"content\": \"contract A {}\"}}",
            "ContractName": "A"
        }
        
        sources, _ = self.verifier.parse_source_code(source_data)
        self.assertIn("A.sol", sources["sources"])

if __name__ == '__main__':
    unittest.main()
