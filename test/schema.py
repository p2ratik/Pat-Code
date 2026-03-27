from pydantic import BaseModel

class AddSchema(BaseModel):
    a : int
    b : int

class AddTool:
    @property
    def schema(self):
        return AddSchema

    def execute(self, params):
        self.schema(**params)

        return params['a'] + params['b']
        
tool = AddTool()

print(tool.execute({"a": 2, "b": 3}))   # ✅ 5
print(tool.execute({"a": 2}))           # ❌ error        