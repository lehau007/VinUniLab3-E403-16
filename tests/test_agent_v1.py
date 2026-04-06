import pytest
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent.agent_v1 import ReActAgentV1

class MockLLM:
    def __init__(self):
        self.model_name = "mock"

def test_parse_action_json():
    agent = ReActAgentV1(llm=MockLLM(), tools=[])
    
    text = '''Thought: I need to search.
Action: {"tool": "search", "args": {"query": "laptop"}}
Observation: '''
    tool_name, args, err = agent._parse_action(text)
    
    assert err is None
    assert tool_name == "search"
    assert args == {"query": "laptop"}

def test_parse_action_function():
    agent = ReActAgentV1(llm=MockLLM(), tools=[])
    
    text = '''Thought: I need to use the calculate tool.
Action: calculate(amount=500, tax=0.1)
Observation: '''
    tool_name, args, err = agent._parse_action(text)
    
    assert err is None
    assert tool_name == "calculate"
    assert args == {"amount": 500, "tax": 0.1}

def test_parse_action_missing():
    agent = ReActAgentV1(llm=MockLLM(), tools=[])
    
    text = '''Thought: I know the answer now.
Final Answer: 550
'''
    tool_name, args, err = agent._parse_action(text)
    
    assert err is not None
    assert "No Action line found" in err

def test_parse_action_vietnamese():
    agent = ReActAgentV1(llm=MockLLM(), tools=[])
    
    text = '''Thought: Tôi cần kiểm tra thông tin sản phẩm và tính thuế nhé.
Action: calc_tax(amount=1000, region="VN")
Observation: '''
    tool_name, args, err = agent._parse_action(text)
    
    assert err is None
    assert tool_name == "calc_tax"
    assert args == {"amount": 1000, "region": "VN"}

def test_extract_final_answer():
    agent = ReActAgentV1(llm=MockLLM(), tools=[])
    
    text = '''Thought: I have the information.
Final Answer: The price is $1000.
'''
    ans = agent._extract_final_answer(text)
    assert ans == "The price is $1000."

def test_agent_v1_complex_query_flow():
    class MockLLMComplex:
        def __init__(self):
            self.step = 0
            self.model_name = "mock"
        
        def generate(self, prompt, system_prompt=None):
            self.step += 1
            if self.step == 1:
                return {"content": 'Thought: I need to check stock for a laptop.\nAction: check_stock(item_name="Laptop")\nObservation: '}
            elif self.step == 2:
                return {"content": 'Thought: Stock is okay. Now let me estimate total for 2 units with coupon SAVE10 to Hanoi.\nAction: estimate_total(product_id="p1", quantity=2, coupon_code="SAVE10", destination="hanoi")\nObservation: '}
            else:
                return {"content": 'Thought: I have calculated everything.\nFinal Answer: The total for 2 laptops is 80000 VND.'}

    from src.tools.registry import create_tool_registry
    class MockRepo:
        def get_products(self): return [{"id": "p1", "name": "Laptop", "stock": 5, "price": 40000, "weight": 2.0}]
        def get_product_by_id(self, pid): return self.get_products()[0] if pid=="p1" else None
        def get_coupons(self): return [{"code": "SAVE10", "discount_pct": 10}]

    repo = MockRepo()
    tools = create_tool_registry(repo)
    agent = ReActAgentV1(llm=MockLLMComplex(), tools=tools)
    
    res = agent.run("Buy 2 laptops to Hanoi with coupon SAVE10")
    assert "80000" in res
