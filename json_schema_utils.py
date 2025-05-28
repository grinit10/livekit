from typing import Dict, Any, Type, Optional
from dataclasses import make_dataclass, field
from typing import Union

def _map_type(type_str: str):
    """Map JSON schema types to Python types"""
    type_mapping = {
        "string": str,
        "number": float,
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return type_mapping.get(type_str, str)
    
def json_schema_to_dataclass(schema: Dict[str, Any], class_name: str = "GeneratedClass") -> Type:
    """Generate a dataclass from a JSON schema.
    
    Args:
        schema: The JSON schema as a dictionary
        class_name: The name for the generated dataclass
        
    Returns:
        A dataclass type that matches the schema
    """
    fields = []
    
    if "properties" not in schema:
        raise ValueError("Schema must have a 'properties' key")
    
    for prop_name, prop_schema in schema["properties"].items():
        field_type = str  # Default type
        default = None
        
        # Handle type field
        if "type" in prop_schema:
            type_info = prop_schema["type"]
            if isinstance(type_info, list):
                # Handle union types (e.g., ["string", "null"])
                types = [t for t in type_info if t != "null"]
                if not types:
                    field_type = Optional[Any]
                else:
                    if len(types) == 1:
                        field_type = _map_type(types[0])
                    else:
                        field_type = Union[tuple(_map_type(t) for t in types)]
                    
                    if "null" in type_info:
                        field_type = Optional[field_type]
                        default = None
            else:
                field_type = _map_type(type_info)
        
        # Add field description as docstring
        if "description" in prop_schema:
            field_metadata = {"metadata": {"description": prop_schema["description"]}}
            fields.append((prop_name, field_type, field(default=default, **field_metadata)))
        else:
            fields.append((prop_name, field_type, default))
    
    return make_dataclass(class_name, fields)


def check_all_fields_populated(schema: Dict[str, Any], session: any):
    required_fields = schema.get('required', [])
    all_props = schema.get('properties', {})
    fields_to_check = required_fields if required_fields else list(all_props.keys())
    
    all_fields_populated = all(
        getattr(session.userdata, field, None) is not None
        for field in fields_to_check
    )
    
    if all_fields_populated:
        # Create kwargs with all populated fields
        kwargs = {
            field: getattr(session.userdata, field)
            for field in fields_to_check
        }
        print(f"All required fields collected: {kwargs}")
        return True
    
    return False
