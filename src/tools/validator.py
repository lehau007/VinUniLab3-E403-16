"""
Input validation layer for tool arguments.
Provides schema validation and type checking before tool execution.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, validator, ValidationError


class ProductLookupParams(BaseModel):
    """Schema for product lookup operations."""
    product_id: Optional[str] = Field(None, min_length=1, description="Product ID (e.g., 'p001')")
    item_name: Optional[str] = Field(None, min_length=1, description="Product name (e.g., 'iPhone 15')")
    
    class Config:
        extra = "forbid"  # Reject unknown fields
    
    @validator('product_id', 'item_name', pre=True)
    def strip_whitespace(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v
    
    def has_lookup_key(self) -> bool:
        """Ensure at least one lookup parameter is provided."""
        return bool(self.product_id or self.item_name)


class ShippingParams(BaseModel):
    """Schema for shipping cost calculation."""
    weight: float = Field(..., ge=0, description="Weight in kg")
    destination: str = Field(..., min_length=1, description="Destination city (e.g., 'Hanoi', 'HCM')")
    
    class Config:
        extra = "forbid"
    
    @validator('weight')
    def validate_weight(cls, v):
        if v < 0 or v > 1000:  # Sanity check: max 1000 kg per shipment
            raise ValueError(f"Weight {v} is outside valid range [0, 1000]")
        return v
    
    @validator('destination', pre=True)
    def normalize_destination(cls, v):
        """Normalize destination names (case-insensitive, trim whitespace)."""
        if isinstance(v, str):
            return v.strip().title()
        return v


class PricingParams(BaseModel):
    """Schema for pricing and discount operations."""
    product_id: str = Field(..., min_length=1, description="Product ID")
    quantity: int = Field(default=1, ge=1, le=10000, description="Quantity to purchase")
    coupon_code: Optional[str] = Field(None, description="Coupon code (optional)")
    destination: str = Field(default="hanoi", description="Destination for shipping")
    
    class Config:
        extra = "forbid"
    
    @validator('product_id', 'coupon_code', pre=True)
    def strip_strings(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v
    
    @validator('quantity')
    def validate_quantity(cls, v):
        if not isinstance(v, int):
            try:
                v = int(v)
            except (ValueError, TypeError):
                raise ValueError(f"Quantity must be integer, got {v}")
        return v


class CouponParams(BaseModel):
    """Schema for coupon lookup."""
    coupon_code: str = Field(..., min_length=1, description="Coupon code")
    
    class Config:
        extra = "forbid"
    
    @validator('coupon_code', pre=True)
    def normalize_code(cls, v):
        if isinstance(v, str):
            return v.strip().upper()
        return v


class ToolValidator:
    """
    Centralized validation service for tool arguments.
    Provides error messages suitable for LLM feedback.
    """
    
    VALIDATORS: Dict[str, Any] = {
        "list_all_products": None,  # No params needed
        "check_stock": ProductLookupParams,
        "check_stock_by_id": ProductLookupParams,
        "get_product_by_id": ProductLookupParams,
        "get_discount": CouponParams,
        "calc_shipping": ShippingParams,
        "estimate_total": PricingParams,
    }
    
    @classmethod
    def validate(cls, tool_name: str, args: Dict[str, Any]) -> tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Validate tool arguments against schema.
        
        Args:
            tool_name: Name of the tool
            args: Arguments to validate
        
        Returns:
            Tuple of (is_valid, error_message, cleaned_args)
            - is_valid: True if validation passed
            - error_message: Human-readable error (None if valid)
            - cleaned_args: Validated and normalized arguments (empty dict if invalid)
        """
        
        # Check if tool exists
        if tool_name not in cls.VALIDATORS:
            return False, f"Unknown tool: {tool_name}. Use only tools from the system prompt.", {}
        
        # list_all_products takes no arguments
        if tool_name == "list_all_products":
            return True, None, {}
        
        # Get the validator model for this tool
        validator_model = cls.VALIDATORS[tool_name]
        if validator_model is None:
            return True, None, args
        
        # Validate arguments
        try:
            validated = validator_model(**args)
            return True, None, validated.dict()
        except ValidationError as e:
            # Build a friendly error message from Pydantic errors
            errors = e.errors()
            error_msgs = []
            for error in errors:
                field = ".".join(str(x) for x in error["loc"])
                msg = error["msg"]
                error_msgs.append(f"{field}: {msg}")
            
            error_text = "; ".join(error_msgs)
            return False, f"Invalid arguments for {tool_name}: {error_text}", {}
        except Exception as e:
            return False, f"Unexpected error validating {tool_name}: {str(e)}", {}
    
    @classmethod
    def get_tool_specs(cls, tool_name: str) -> Optional[str]:
        """
        Get a human-readable spec for a tool to help LLM correct mistakes.
        
        Args:
            tool_name: Name of the tool
        
        Returns:
            String description of expected parameters, or None if tool unknown
        """
        
        specs = {
            "list_all_products": "No parameters required. Usage: list_all_products()",
            "check_stock": "Parameters: product_id (string, e.g., 'p001') OR item_name (string, e.g., 'iPhone 15'). At least one required.",
            "check_stock_by_id": "Parameters: product_id (string, required, e.g., 'p001')",
            "get_product_by_id": "Parameters: product_id (string, required, e.g., 'p001')",
            "get_discount": "Parameters: coupon_code (string, required, e.g., 'WINNER')",
            "calc_shipping": "Parameters: weight (number >= 0, required, in kg), destination (string, required, e.g., 'Hanoi' or 'HCM')",
            "estimate_total": "Parameters: product_id (string, required), quantity (integer >= 1, default=1), coupon_code (string, optional), destination (string, default='hanoi')",
        }
        
        return specs.get(tool_name)
