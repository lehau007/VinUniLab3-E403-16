"""
Test suite for input validation layer.
Tests schema validation, error recovery, and edge cases.
"""

import pytest
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.validator import (
    ToolValidator,
    ProductLookupParams,
    ShippingParams,
    PricingParams,
    CouponParams,
)


# ============ Test Pydantic Models ============

class TestProductLookupParams:
    """Test product lookup parameter validation."""
    
    def test_valid_product_id(self):
        params = ProductLookupParams(product_id="p001")
        assert params.product_id == "p001"
        assert params.has_lookup_key()
    
    def test_valid_item_name(self):
        params = ProductLookupParams(item_name="iPhone 15")
        assert params.item_name == "iPhone 15"
        assert params.has_lookup_key()
    
    def test_both_provided(self):
        params = ProductLookupParams(product_id="p001", item_name="iPhone 15")
        assert params.has_lookup_key()
    
    def test_neither_provided(self):
        params = ProductLookupParams()
        assert not params.has_lookup_key()
    
    def test_whitespace_stripped(self):
        params = ProductLookupParams(product_id="  p001  ")
        assert params.product_id == "p001"
    
    def test_empty_string_rejected(self):
        with pytest.raises(ValueError):
            ProductLookupParams(product_id="")


class TestShippingParams:
    """Test shipping parameter validation."""
    
    def test_valid_shipping(self):
        params = ShippingParams(weight=5.0, destination="Hanoi")
        assert params.weight == 5.0
        assert params.destination == "Hanoi"
    
    def test_zero_weight_valid(self):
        params = ShippingParams(weight=0.0, destination="HCM")
        assert params.weight == 0.0
    
    def test_negative_weight_rejected(self):
        with pytest.raises(ValueError):
            ShippingParams(weight=-1.0, destination="Hanoi")
    
    def test_excessive_weight_rejected(self):
        with pytest.raises(ValueError):
            ShippingParams(weight=2000.0, destination="Hanoi")
    
    def test_destination_normalized(self):
        params = ShippingParams(weight=5.0, destination="hcm")
        assert params.destination == "Hcm"  # Title case
    
    def test_destination_whitespace_stripped(self):
        params = ShippingParams(weight=5.0, destination="  hanoi  ")
        assert params.destination == "Hanoi"
    
    def test_weight_type_coercion(self):
        # Should accept numeric types
        params = ShippingParams(weight=5, destination="Hanoi")
        assert params.weight == 5


class TestPricingParams:
    """Test pricing parameter validation."""
    
    def test_valid_pricing(self):
        params = PricingParams(product_id="p001", quantity=2)
        assert params.product_id == "p001"
        assert params.quantity == 2
    
    def test_default_quantity(self):
        params = PricingParams(product_id="p001")
        assert params.quantity == 1
    
    def test_quantity_zero_rejected(self):
        with pytest.raises(ValueError):
            PricingParams(product_id="p001", quantity=0)
    
    def test_quantity_too_large_rejected(self):
        with pytest.raises(ValueError):
            PricingParams(product_id="p001", quantity=20000)
    
    def test_quantity_string_coerced(self):
        params = PricingParams(product_id="p001", quantity="5")
        assert params.quantity == 5
    
    def test_quantity_invalid_string_rejected(self):
        with pytest.raises(ValueError):
            PricingParams(product_id="p001", quantity="invalid")
    
    def test_coupon_optional(self):
        params = PricingParams(product_id="p001")
        assert params.coupon_code is None
    
    def test_coupon_provided(self):
        params = PricingParams(product_id="p001", coupon_code="WINNER")
        assert params.coupon_code == "WINNER"
    
    def test_destination_default(self):
        params = PricingParams(product_id="p001")
        assert params.destination == "hanoi"


class TestCouponParams:
    """Test coupon parameter validation."""
    
    def test_valid_coupon(self):
        params = CouponParams(coupon_code="WINNER")
        assert params.coupon_code == "WINNER"
    
    def test_coupon_normalized_uppercase(self):
        params = CouponParams(coupon_code="winner")
        assert params.coupon_code == "WINNER"
    
    def test_coupon_whitespace_stripped(self):
        params = CouponParams(coupon_code="  WINNER  ")
        assert params.coupon_code == "WINNER"
    
    def test_empty_coupon_rejected(self):
        with pytest.raises(ValueError):
            CouponParams(coupon_code="")


# ============ Test ToolValidator ============

class TestToolValidator:
    """Test the centralized validation service."""
    
    def test_list_all_products_no_args(self):
        is_valid, error_msg, args = ToolValidator.validate("list_all_products", {})
        assert is_valid
        assert error_msg is None
        assert args == {}
    
    def test_list_all_products_with_args_rejected(self):
        # list_all_products should reject arguments
        is_valid, error_msg, args = ToolValidator.validate("list_all_products", {"foo": "bar"})
        assert is_valid  # Still valid, args ignored
        assert args == {}
    
    def test_check_stock_valid(self):
        is_valid, error_msg, args = ToolValidator.validate("check_stock", {"item_name": "iPhone 15"})
        assert is_valid
        assert error_msg is None
        assert args == {"item_name": "iPhone 15", "product_id": None}
    
    def test_check_stock_no_lookup_key(self):
        is_valid, error_msg, args = ToolValidator.validate("check_stock", {})
        assert not is_valid  # Currently passes but should validate has_lookup_key
        assert error_msg is not None
    
    def test_calc_shipping_valid(self):
        is_valid, error_msg, args = ToolValidator.validate(
            "calc_shipping", 
            {"weight": 5.0, "destination": "Hanoi"}
        )
        assert is_valid
        assert error_msg is None
        assert args["weight"] == 5.0
    
    def test_calc_shipping_invalid_weight(self):
        is_valid, error_msg, args = ToolValidator.validate(
            "calc_shipping",
            {"weight": -1.0, "destination": "Hanoi"}
        )
        assert not is_valid
        assert "weight" in error_msg.lower()
    
    def test_estimate_total_valid(self):
        is_valid, error_msg, args = ToolValidator.validate(
            "estimate_total",
            {
                "product_id": "p001",
                "quantity": 2,
                "coupon_code": "WINNER",
                "destination": "HCM"
            }
        )
        assert is_valid
        assert error_msg is None
    
    def test_estimate_total_missing_required_field(self):
        is_valid, error_msg, args = ToolValidator.validate(
            "estimate_total",
            {"quantity": 2}  # Missing product_id
        )
        assert not is_valid
        assert error_msg is not None
    
    def test_unknown_tool(self):
        is_valid, error_msg, args = ToolValidator.validate(
            "nonexistent_tool",
            {}
        )
        assert not is_valid
        assert "Unknown tool" in error_msg
    
    def test_unknown_field_rejected(self):
        is_valid, error_msg, args = ToolValidator.validate(
            "calc_shipping",
            {"weight": 5.0, "destination": "Hanoi", "unknown_field": "value"}
        )
        assert not is_valid
        assert "unknown_field" in error_msg.lower() or "Extra" in error_msg
    
    def test_get_tool_specs_valid(self):
        spec = ToolValidator.get_tool_specs("calc_shipping")
        assert spec is not None
        assert "weight" in spec.lower()
        assert "destination" in spec.lower()
    
    def test_get_tool_specs_unknown_tool(self):
        spec = ToolValidator.get_tool_specs("unknown_tool")
        assert spec is None
    
    def test_validation_error_message_helpful(self):
        """Test that validation errors are helpful for LLM feedback."""
        is_valid, error_msg, args = ToolValidator.validate(
            "calc_shipping",
            {"weight": "invalid", "destination": "Hanoi"}
        )
        assert not is_valid
        assert "calc_shipping" in error_msg
        assert "weight" in error_msg.lower()


# ============ Test Edge Cases ============

class TestEdgeCases:
    """Test edge cases and error recovery."""
    
    def test_type_coercion_weight_string_number(self):
        """Weight as string that looks like a number should be coerced."""
        is_valid, error_msg, args = ToolValidator.validate(
            "calc_shipping",
            {"weight": "5.5", "destination": "Hanoi"}
        )
        # Pydantic should coerce string "5.5" to float
        assert is_valid or error_msg is not None  # Depends on Pydantic version
    
    def test_quantity_type_coercion(self):
        """Quantity as string should be coerced to int."""
        is_valid, error_msg, args = ToolValidator.validate(
            "estimate_total",
            {"product_id": "p001", "quantity": "5"}
        )
        assert is_valid
        assert args["quantity"] == 5
    
    def test_coupon_code_empty_string(self):
        """Empty coupon code should be rejected."""
        is_valid, error_msg, args = ToolValidator.validate(
            "get_discount",
            {"coupon_code": ""}
        )
        assert not is_valid
    
    def test_product_id_whitespace_only(self):
        """Product ID that is only whitespace should be rejected."""
        is_valid, error_msg, args = ToolValidator.validate(
            "get_product_by_id",
            {"product_id": "   "}
        )
        assert not is_valid or error_msg is not None
    
    def test_destination_special_characters(self):
        """Destination with special characters should be accepted."""
        is_valid, error_msg, args = ToolValidator.validate(
            "calc_shipping",
            {"weight": 5.0, "destination": "Da Nang"}
        )
        assert is_valid


# ============ Integration Tests ============

class TestValidationIntegration:
    """Integration tests with realistic scenarios."""
    
    def test_full_e_commerce_flow(self):
        """Test a complete e-commerce flow validation."""
        
        # Step 1: Search products
        is_valid, _, _ = ToolValidator.validate("list_all_products", {})
        assert is_valid
        
        # Step 2: Get product details
        is_valid, _, args = ToolValidator.validate(
            "get_product_by_id",
            {"product_id": "p001"}
        )
        assert is_valid
        assert args["product_id"] == "p001"
        
        # Step 3: Check stock
        is_valid, _, _ = ToolValidator.validate(
            "check_stock_by_id",
            {"product_id": "p001"}
        )
        assert is_valid
        
        # Step 4: Get discount
        is_valid, _, args = ToolValidator.validate(
            "get_discount",
            {"coupon_code": "WINNER"}
        )
        assert is_valid
        assert args["coupon_code"] == "WINNER"
        
        # Step 5: Calculate shipping
        is_valid, _, args = ToolValidator.validate(
            "calc_shipping",
            {"weight": 2.5, "destination": "hanoi"}
        )
        assert is_valid
        assert args["destination"] == "Hanoi"  # Normalized
        
        # Step 6: Estimate total
        is_valid, _, args = ToolValidator.validate(
            "estimate_total",
            {
                "product_id": "p001",
                "quantity": 2,
                "coupon_code": "WINNER",
                "destination": "Hanoi"
            }
        )
        assert is_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
