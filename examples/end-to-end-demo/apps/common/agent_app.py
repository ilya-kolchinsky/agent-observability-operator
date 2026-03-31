"""Shared agent demo app factory using LangChain."""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Literal

from fastapi import FastAPI
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain_community.chat_models import ChatOllama
from langchain_core.tools import Tool
from openai import OpenAI
from pydantic import BaseModel, Field

from common.logging_config import configure_logging, install_request_logging
from common.mcp_client import call_tool_sync


class AgentRequest(BaseModel):
    """Request payload for the demo agent."""

    prompt: str = Field(..., examples=["What's the weather in Seattle?"])
    max_iterations: int = Field(default=10, description="Maximum agent iterations")


class ScenarioConfig:
    """Configuration for a specific demo scenario."""

    def __init__(
        self,
        service_name: str,
        scenario: Literal["no-existing", "partial-existing", "full-existing"],
        mcp_server_url: str,
        llm_base_url: str,
        llm_model: str,
    ):
        self.service_name = service_name
        self.scenario = scenario
        self.mcp_server_url = mcp_server_url
        self.llm_base_url = llm_base_url
        self.llm_model = llm_model


class DemoLangchainAgent:
    """LangChain-based agent with MCP tools and LLM reasoning."""

    def __init__(self, logger: logging.Logger, config: ScenarioConfig) -> None:
        self._logger = logger
        self._config = config

        # Initialize LLM (Ollama)
        self._llm = ChatOllama(
            base_url=config.llm_base_url,
            model=config.llm_model,
            temperature=0.0,  # Deterministic for reliable tool calling
            num_predict=256,  # Limit output length to prevent hallucination
        )

        # Initialize OpenAI client pointing to Ollama's OpenAI-compatible endpoint
        # This is used for LLM-as-a-judge validation of the agent's answers
        openai_base_url = config.llm_base_url.rstrip('/') + '/v1'
        self._openai_client = OpenAI(
            base_url=openai_base_url,
            api_key="dummy",  # Ollama doesn't require a real key
        )
        self._logger.info("openai_client_initialized base_url=%s", openai_base_url)

        # Create MCP tools
        self._tools = self._create_mcp_tools()

        # Create agent prompt (ReAct style with example)
        prompt = PromptTemplate.from_template("""Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format EXACTLY:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Here is an example:

Question: What is the weather in Tokyo?
Thought: I need to get weather information for Tokyo
Action: get_weather
Action Input: Tokyo
Observation: Weather in Tokyo: clear, 18°C
Thought: I now know the final answer
Final Answer: The weather in Tokyo is clear with a temperature of 18°C.

Now answer the actual question:

Question: {input}
Thought:{agent_scratchpad}""")

        # Create agent (ReAct agent works with any LLM)
        agent = create_react_agent(self._llm, self._tools, prompt)

        # Custom error handler for phi's single-line format
        def handle_phi_format(error) -> str:
            """Try to extract tool and input from phi's format when standard parsing fails."""
            import re
            error_text = str(error) if error else ""
            if hasattr(error, 'llm_output'):
                error_text = error.llm_output
            elif hasattr(error, 'observation'):
                error_text = error.observation

            match = re.search(r'Action:\s*(\w+),?\s*Action Input:\s*(.+?)(?:\n|Question|Thought|$)', error_text, re.IGNORECASE | re.DOTALL)
            if match:
                return f"Action: {match.group(1).strip()}\nAction Input: {match.group(2).strip()}"
            return error_text

        self._agent_executor = AgentExecutor(
            agent=agent,
            tools=self._tools,
            verbose=True,
            max_iterations=6,  # Allow a few retries for small model
            handle_parsing_errors=True,  # Return error string instead of raising
            return_intermediate_steps=True,
        )

        self._logger.info(
            "agent_initialized scenario=%s llm_model=%s tools=%s",
            config.scenario,
            config.llm_model,
            [tool.name for tool in self._tools],
        )

    def _create_mcp_tools(self) -> list[Tool]:
        """Create LangChain tools that wrap MCP server tools."""

        def get_weather_tool(location: str) -> str:
            """Get weather information for a location."""
            self._logger.info("tool_call_start tool=get_weather location=%s", location)
            try:
                result = call_tool_sync(
                    server_url=self._config.mcp_server_url,
                    tool_name="get_weather",
                    arguments={"location": location},
                )
                content = result.get("structured_content", {})
                response = f"Weather in {location}: {content.get('forecast', 'unknown')}, {content.get('temperature_c', 'n/a')}°C"
                self._logger.info("tool_call_end tool=get_weather response=%s", response)
                return response
            except Exception as e:
                self._logger.error("tool_call_error tool=get_weather error=%s", str(e))
                return f"Error getting weather: {str(e)}"

        return [
            Tool(
                name="get_weather",
                func=get_weather_tool,
                description="Get weather for a location. Input: city name like Seattle or London",
            ),
        ]

    def _validate_answer(self, query: str, answer: str) -> dict[str, Any]:
        """Use OpenAI SDK (LLM-as-a-judge) to validate the agent's answer.

        This demonstrates a realistic production pattern where one LLM validates
        another's output for coherence, relevance, and correctness.
        """
        self._logger.info("validation_start query=%s", query[:50])

        try:
            validation_prompt = f"""You are a judge evaluating an AI agent's answer.

Question: {query}
Answer: {answer}

Evaluate this answer on:
1. Coherence: Does it make sense?
2. Relevance: Does it address the question?
3. Completeness: Does it provide useful information?

Rate from 1-5 (5 is best) and provide a brief explanation.
Format: "Rating: X/5 - explanation"
"""

            response = self._openai_client.chat.completions.create(
                model=self._config.llm_model,
                messages=[{"role": "user", "content": validation_prompt}],
                temperature=0.0,
                max_tokens=100,
            )

            judgment = response.choices[0].message.content.strip()

            # Extract rating from judgment (simple regex)
            rating_match = re.search(r'Rating:\s*(\d)', judgment)
            rating = int(rating_match.group(1)) if rating_match else 3

            self._logger.info("validation_end rating=%d judgment=%s", rating, judgment[:100])

            return {
                "rating": rating,
                "judgment": judgment,
                "passed": rating >= 3,
            }
        except Exception as e:
            self._logger.error("validation_error error=%s", str(e))
            return {
                "rating": 0,
                "judgment": f"Validation failed: {str(e)}",
                "passed": False,
            }

    def run(self, request: AgentRequest) -> dict[str, Any]:
        """Execute the agent with LLM guidance and tool calls."""
        self._logger.info("agent_run_start scenario=%s prompt=%s", self._config.scenario, request.prompt)

        try:
            from langchain_core.messages import HumanMessage

            # Step 1: Ask LLM to extract the location from the query
            location_prompt = f"Extract just the city name from this question: '{request.prompt}'. Reply with only the city name, nothing else."
            location_response = self._llm.invoke([HumanMessage(content=location_prompt)])
            location = location_response.content.strip().split('\n')[0].strip('."\'')

            # Fallback to common cities if extraction fails
            if not location or len(location) > 50:
                cities = ["Seattle", "Austin", "London", "New York", "Tokyo", "San Francisco"]
                location = "Seattle"  # default
                for city in cities:
                    if city.lower() in request.prompt.lower():
                        location = city
                        break

            self._logger.info("extracted_location location=%s", location)

            # Step 2: Call the weather tool through LangChain (for instrumentation)
            tool = self._tools[0]  # get_weather tool
            weather_result = tool.func(location)

            # Step 3: Ask LLM to format a friendly response
            format_prompt = f"The weather tool returned: '{weather_result}'. Write a brief, friendly response to the question '{request.prompt}'."
            final_response = self._llm.invoke([HumanMessage(content=format_prompt)])
            output = final_response.content.strip()

            # Step 4: Validate answer using OpenAI SDK (LLM-as-a-judge)
            validation = self._validate_answer(request.prompt, output)

            self._logger.info(
                "agent_run_end scenario=%s output=%s validation_rating=%d",
                self._config.scenario,
                output,
                validation.get("rating", 0),
            )

            return {
                "input": request.prompt,
                "output": output,
                "intermediate_steps": 2,  # location extraction + weather call
                "validation": validation,
            }
        except Exception as e:
            self._logger.error("agent_run_error scenario=%s error=%s", self._config.scenario, str(e))
            return {
                "input": request.prompt,
                "output": "Failed to answer the query.",
                "error": str(e)[:200],
            }

    def _parse_output(self, prompt: str, output: str, intermediate_steps: list) -> str:
        """Simple naive parsing to extract answer from LLM output or intermediate steps."""
        # If the output looks reasonable, use it
        if output and output != "Agent stopped due to iteration limit or time limit.":
            return output

        # Extract from weather tool results
        for step in reversed(intermediate_steps):
            if isinstance(step, tuple) and len(step) >= 2:
                action, observation = step[0], step[1]
                if hasattr(action, 'tool') and 'weather' in action.tool.lower():
                    return str(observation)

        return output if output else "I couldn't get the weather information."


def create_agent_app(config: ScenarioConfig) -> FastAPI:
    """Create a FastAPI app for a specific instrumentation scenario."""

    logger = configure_logging(config.service_name)
    agent = DemoLangchainAgent(logger=logger, config=config)
    app = FastAPI(title=config.service_name, version="0.1.0")
    install_request_logging(app, logger)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "service": config.service_name}

    @app.post("/run")
    def run_agent(request: AgentRequest) -> dict[str, Any]:
        result = agent.run(request)
        return {
            "service": config.service_name,
            "scenario": config.scenario,
            "result": result,
        }

    logger.info(
        "agent_app_ready service=%s scenario=%s llm=%s mcp_server=%s",
        config.service_name,
        config.scenario,
        config.llm_model,
        config.mcp_server_url,
    )
    return app


def build_scenario_config(
    service_name: str,
    scenario: Literal["no-existing", "partial-existing", "full-existing"],
) -> ScenarioConfig:
    """Build scenario configuration from environment variables."""

    mcp_server_url = os.getenv("MCP_SERVER_URL", "http://mcp-server:8000")
    llm_base_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
    llm_model = os.getenv("OLLAMA_MODEL", "phi")

    return ScenarioConfig(
        service_name=service_name,
        scenario=scenario,
        mcp_server_url=mcp_server_url,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
    )
