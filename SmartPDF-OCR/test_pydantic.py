
from pydantic import BaseModel, Field
print("Pydantic import success")
class User(BaseModel):
    name: str = Field(..., title="Name")
print(User(name="test"))
print(Field().json_schema_extra)
