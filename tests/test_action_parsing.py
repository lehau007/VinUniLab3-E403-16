"""
Test suite for action parsing and syntax recovery in ReAct agents.
Tests the syntax fixer and improved error recovery mechanisms.
"""

import pytest
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent.agent_v1 import ReActAgentV1


class MockLLMForParsing:
    """Mock LLM for testing parsing without making actual API calls."""
    def __init__(self):
        self.model_name = "mock-parser"


class TestSyntaxRecovery:
    """Test the _attempt_syntax_fix method."""
    
    def test_fix_missing_closing_paren(self):
        """Test fixing missing closing parenthesis."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        # Missing single closing paren
        fixed = agent._attempt_syntax_fix("check_stock(product_id='p001'")
        assert fixed == "check_stock(product_id='p001')"
        
        # Missing multiple closing parens
        fixed = agent._attempt_syntax_fix("outer(inner(value")
        assert fixed == "outer(inner(value))"
    
    def test_no_fix_needed_already_valid(self):
        """Test that valid syntax is not modified."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        valid = "check_stock(product_id='p001')"
        fixed = agent._attempt_syntax_fix(valid)
        assert fixed == valid
    
    def test_fix_with_whitespace(self):
        """Test fixing with extra whitespace."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        fixed = agent._attempt_syntax_fix("  calc_shipping(weight=5.0, destination='Hanoi'  ")
        # Should add closing paren
        assert fixed.count('(') == fixed.count(')')


class TestActionParsingWithRecovery:
    """Test action parsing with syntax recovery integrated."""
    
    def test_parse_with_missing_closing_paren(self):
        """Test that missing closing paren is fixed and parsed correctly."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        text = """Thought: I need to check stock.
Action: check_stock(product_id='p001'
Observation: """
        
        tool_name, args, error = agent._parse_action(text)
        assert error is None
        assert tool_name == "check_stock"
        assert args == {"product_id": "p001"}
    
    def test_parse_function_style_with_recovery(self):
        """Test various function-style actions that need recovery."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        # Malformed but recoverable
        text = "Action: calc_shipping(weight=5.0, destination='Hanoi'"
        tool_name, args, error = agent._parse_action(text)
        assert error is None
        assert tool_name == "calc_shipping"
        assert args["weight"] == 5.0
        assert args["destination"] == "Hanoi"
    
    def test_parse_json_action(self):
        """Test JSON format actions are still parsed correctly."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        text = '''Action: {"tool": "get_product_by_id", "args": {"product_id": "p001"}}'''
        tool_name, args, error = agent._parse_action(text)
        assert error is None
        assert tool_name == "get_product_by_id"
        assert args == {"product_id": "p001"}
    
    def test_parse_with_code_fences(self):
        """Test parsing with markdown code fences."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        text = '''```json
Action: check_stock(item_name="iPhone 15"
```'''
        tool_name, args, error = agent._parse_action(text)
        assert error is None
        assert tool_name == "check_stock"
        assert args == {"item_name": "iPhone 15"}


class TestActionParsingEdgeCases:
    """Test edge cases in action parsing."""
    
    def test_multiple_action_lines(self):
        """Test that latest Action line is used."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        text = """Action: wrong_tool(arg="old")
Action: correct_tool(arg="new")"""
        tool_name, args, error = agent._parse_action(text)
        assert error is None
        assert tool_name == "correct_tool"
    
    def test_mixed_quotes_in_arguments(self):
        """Test parsing with mixed quote styles."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        text = """Action: calc_shipping(weight=5.0, destination='Hanoi')"""
        tool_name, args, error = agent._parse_action(text)
        assert error is None
        assert args["destination"] == "Hanoi"
    
    def test_unquoted_string_values(self):
        """Test parsing of unquoted string values."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        text = "Action: calc_shipping(weight=5.0, destination=Hanoi)"
        tool_name, args, error = agent._parse_action(text)
        assert error is None
        assert args["destination"] == "Hanoi"
    
    def test_nested_parentheses(self):
        """Test parsing with nested function calls."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        text = "Action: some_tool(nested_arg=some_func('value')"
        tool_name, args, error = agent._parse_action(text)
        # Should fix the missing paren
        assert error is None or "Invalid action format" in error
    
    def test_vietnamese_text_in_action(self):
        """Test parsing with Vietnamese characters."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        text = """Thought: Tôi cần kiểm tra hàng.
Action: check_stock(item_name='iPhone 15')"""
        tool_name, args, error = agent._parse_action(text)
        assert error is None
        assert tool_name == "check_stock"
    
    def test_completely_invalid_action(self):
        """Test that truly invalid actions return an error."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        text = "Thought: Let me think about this."  # No Action line
        tool_name, args, error = agent._parse_action(text)
        assert error is not None
        assert "No Action line found" in error
    
    def test_malformed_json_falls_back_to_function(self):
        """Test that malformed JSON falls back to function parsing."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        text = '''Action: {"tool": "bad json without closing'''
        tool_name, args, error = agent._parse_action(text)
        # Should fall back to function parsing and fail gracefully
        assert error is not None


class TestParseArgsVariations:
    """Test the _parse_args method with various formats."""
    
    def test_parse_json_args(self):
        """Test parsing JSON object arguments."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        args_text = '{"key1": "value1", "key2": 123}'
        result = agent._parse_args(args_text)
        assert result == {"key1": "value1", "key2": 123}
    
    def test_parse_key_value_pairs(self):
        """Test parsing key=value format."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        args_text = "product_id='p001', quantity=2"
        result = agent._parse_args(args_text)
        assert result == {"product_id": "p001", "quantity": 2}
    
    def test_parse_single_value(self):
        """Test parsing single value argument."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        args_text = "'single_string_arg'"
        result = agent._parse_args(args_text)
        assert result == {"value": "single_string_arg"}
    
    def test_parse_empty_args(self):
        """Test parsing empty argument string."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        result = agent._parse_args("")
        assert result == {}
    
    def test_parse_numeric_args(self):
        """Test parsing numeric arguments."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        args_text = "value=42"
        result = agent._parse_args(args_text)
        assert result == {"value": 42}
        
        args_text = "pi=3.14"
        result = agent._parse_args(args_text)
        assert result == {"pi": 3.14}


class TestComprehensiveParsing:
    """Comprehensive real-world parsing scenarios."""
    
    def test_realistic_product_lookup_flow(self):
        """Test realistic product lookup action."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        # First step: list products
        text = "Action: list_all_products("
        tool_name, args, error = agent._parse_action(text)
        assert error is None
        assert tool_name == "list_all_products"
    
    def test_realistic_pricing_flow(self):
        """Test realistic pricing calculation."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        text = """Action: estimate_total(product_id='p001', quantity=2, coupon_code='WINNER', destination='Hanoi')"""
        tool_name, args, error = agent._parse_action(text)
        assert error is None
        assert tool_name == "estimate_total"
        assert args["quantity"] == 2
    
    def test_recovery_from_llm_mistakes(self):
        """Test recovery from common LLM mistakes."""
        agent = ReActAgentV1(llm=MockLLMForParsing(), tools=[])
        
        # Mistake 1: Missing closing paren
        text = "Action: calc_shipping(weight=5.0, destination='HCM'"
        tool_name, args, error = agent._parse_action(text)
        assert error is None
        
        # Mistake 2: Extra spaces
        text = "Action:   check_stock  (  item_name = 'iPhone'  )"
        tool_name, args, error = agent._parse_action(text)
        assert error is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
