from agents import Agent, Runner, OpenAIChatCompletionsModel, AsyncOpenAI
import os

os.environ["OPENAI_API_KEY"] ="No Need"

model = OpenAIChatCompletionsModel(
    model="llama3.2:latest",
    openai_client=AsyncOpenAI(base_url="http://localhost:11434/v1")
)

agent = Agent(name="Assistant",
              instructions="Ты полезный помощник.",
              model=model)

result = Runner.run_sync(agent, "Составьте план питания на неделю.")
print(result.final_output)