from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from typing import Annotated, TypedDict
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)
from langgraph.graph import StateGraph, START, END, MessagesState
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt
from loguru import logger
import uuid
from langchain_core.runnables import RunnableLambda
from dotenv import load_dotenv
import json
import re
# Import the Twitter client
from twitter_client import post_ip_minted_tweet

# Load environment variables from .env file
load_dotenv()

# Define our state
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], "The messages in the conversation"]
    sender: str
    thread_id: str

# Create DALL-E tool
@tool
def generate_image(prompt: str) -> str:
    """Generate an image using DALL-E 3 based on the prompt."""
    dalle = DallEAPIWrapper()
    image_url = dalle.run(prompt)
    return f"Generated image URL: {image_url}"

# Create human feedback tool
@tool
def get_human_feedback(image_url: str) -> str:
    """Get human feedback on whether to upload the image to IPFS."""
    return "feedback"


# Create local file upload tool
@tool
def upload_local_file(file_path: str) -> str:
    """
    Upload a local image or video file.
    
    Args:
        file_path: Path to the local file to upload
    
    Returns:
        The file path if valid, or an error message if invalid
    """
    # Validate the file path
    import os
    if not os.path.exists(file_path):
        return f"Error: File not found at {file_path}"
    
    # Check if it's a valid image or video file
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mov', '.avi', '.webm']
    file_ext = os.path.splitext(file_path)[1].lower()
    
    if file_ext not in valid_extensions:
        return f"Error: Unsupported file type. Please use one of: {', '.join(valid_extensions)}"
    
    # Check file size (limit to 100MB)
    file_size = os.path.getsize(file_path)
    if file_size > 100 * 1024 * 1024:  # 100MB in bytes
        return f"Error: File size too large. Maximum size is 100MB."
    
    # Return the file path for further processing
    return file_path

# Create Luma video generation tool (placeholder for now)
@tool
def generate_luma_video(prompt: str) -> str:
    """
    Generate a video using Luma AI based on the prompt.
    
    Args:
        prompt: Description of the video to generate
    
    Returns:
        A placeholder URL for the generated video
    """
    # This is a placeholder implementation
    # In a real implementation, you would call the Luma API here
    print(f"Generating video with Luma AI: {prompt}")
    
    # Return a placeholder URL
    # In a real implementation, this would be the URL returned by the Luma API
    import uuid
    return f"https://example.com/luma-video-{uuid.uuid4()}.mp4"


# Create human feedback tool
@tool
def get_human_feedback(image_url: str) -> str:
    """Get human feedback on whether to upload the image to IPFS."""
    response = interrupt(
        {
            "message": f"Image has been generated: {image_url}\nWould you like to upload this to IPFS? (yes/no)"
        }
    )
    logger.info(f"Human feedback received: {response['data']}")
    return response["data"]


async def setup_mcp_client():
    """Setup MCP client and get IPFS tools"""
    async with MultiServerMCPClient() as client:
        await client.connect_to_server(
            "story_server",
            command="python",
            args=["../story-sdk-mcp/server.py"],
        )
        ipfs_tools = [
            tool
            for tool in client.get_tools()
            if tool.name
            in [
                "upload_image_to_ipfs",
                "create_ip_metadata",
                "mint_and_register_ip_with_terms",
                "mint_license_tokens",
            ]
        ]
        return ipfs_tools


class State(MessagesState):
    """Simple state."""


def create_graph(ipfs_tools):
    # Get the specific tools by name
    try:
        upload_to_ipfs_tool = next(
            tool for tool in ipfs_tools if tool.name == "upload_image_to_ipfs"
        )
        create_metadata_tool = next(
            tool for tool in ipfs_tools if tool.name == "create_ip_metadata"
        )
        mint_register_ip_tool = next(
            tool
            for tool in ipfs_tools
            if tool.name == "mint_and_register_ip_with_terms"
        )
        mint_license_tokens_tool = next(
            tool for tool in ipfs_tools if tool.name == "mint_license_tokens"
        )
    except StopIteration:
        print("Error: Could not find required tools. Available tools:")
        for tool in ipfs_tools:
            print(f"- {tool.name}")
        raise ValueError(
            "Missing required tools. Make sure all required tools are available."
        )

    # Initialize model with all tools available
    model = ChatOpenAI(model="gpt-4o").bind_tools(
        [
            generate_image,
            upload_to_ipfs_tool,
            create_metadata_tool,
            mint_register_ip_tool,
            mint_license_tokens_tool,
            upload_local_file,
            generate_luma_video
        ]
    )

    # Simpler model for negotiation and other tasks
    simple_model = ChatOpenAI(model="gpt-4o-mini")

    class CallLLM:
        async def ainvoke(self, state, config=None):
            messages = state["messages"]
            response = await model.ainvoke(messages)
            return {"messages": [response]}

    class RunTool:
        async def ainvoke(self, state, config=None):
            new_messages = []
            tools = {
                "generate_image": generate_image,
                "upload_image_to_ipfs": upload_to_ipfs_tool,
                "upload_local_file": upload_local_file,
                "generate_luma_video": generate_luma_video
            }
            last_message = state["messages"][-1]

            for tool_call in last_message.tool_calls:
                try:
                    tool = tools[tool_call["name"]]

                    # Handle local file upload
                    if tool_call["name"] == "upload_local_file":
                        file_path = tool_call["args"].get("file_path", "")
                        result = tool(file_path)
                        
                        if isinstance(result, str) and result.startswith("Error:"):
                            # If there's an error, return it
                            new_messages.append(
                                ToolMessage(
                                    content=result,
                                    name=tool_call["name"],
                                    tool_call_id=tool_call["id"],
                                )
                            )
                        else:
                            # If successful, return the file path for review
                            new_messages.append(
                                ToolMessage(
                                    content=f"File path: {result}",
                                    name=tool_call["name"],
                                    tool_call_id=tool_call["id"],
                                )
                            )
                    # Handle Luma video generation
                    elif tool_call["name"] == "generate_luma_video":
                        prompt = tool_call["args"].get("prompt", "")
                        result = tool(prompt)
                        new_messages.append(
                            ToolMessage(
                                content=f"Generated video URL: {result}",
                                name=tool_call["name"],
                                tool_call_id=tool_call["id"],
                            )
                        )
                    # Extract just the string value for image_data if that's the parameter
                    elif (
                        tool_call["name"] == "upload_image_to_ipfs"
                        and "image_data" in tool_call["args"]
                    ):
                        # Make sure we're passing just the URL string, not a complex object
                        image_url = tool_call["args"]["image_data"]
                        result = await tool.ainvoke({"image_data": image_url})
                        
                        # Make sure result is a string
                        if not isinstance(result, str):
                            result = str(result)
                        
                        new_messages.append(
                            ToolMessage(
                                content=result,
                                name=tool_call["name"],
                                tool_call_id=tool_call["id"],
                            )
                        )
                    else:
                        result = await tool.ainvoke(tool_call["args"])

                        # Make sure result is a string
                        if not isinstance(result, str):
                            result = str(result)
                        
                        new_messages.append(
                            ToolMessage(
                                content=result,
                                name=tool_call["name"],
                                tool_call_id=tool_call["id"],
                            )
                        )

                except Exception as e:
                    new_messages.append(
                        ToolMessage(
                            content=f"Error executing tool: {str(e)}",
                            name=tool_call["name"],
                            tool_call_id=tool_call["id"],
                        )
                    )

            # Determine next node based on the tool that was called
            if any(msg.name == "generate_image" for msg in new_messages) or \
               any(msg.name == "generate_luma_video" for msg in new_messages) or \
               any(msg.name == "upload_local_file" for msg in new_messages):
                return {"messages": state["messages"] + new_messages, "next": "human_review_node"}
            
            return {"messages": state["messages"] + new_messages}

    class RunIPFSTool:
        async def ainvoke(self, state, config=None):
            new_messages = []
            last_message = state["messages"][-1]

            for tool_call in last_message.tool_calls:
                try:
                    # Extract just the string value for image_data if that's the parameter
                    if "image_data" in tool_call["args"]:
                        # Make sure we're passing just the URL string, not a complex object
                        image_url = tool_call["args"]["image_data"]
                        result = await upload_to_ipfs_tool.ainvoke(
                            {"image_data": image_url}
                        )
                    else:
                        result = await upload_to_ipfs_tool.ainvoke(tool_call["args"])

                    # Make sure result is a string
                    if not isinstance(result, str):
                        result = str(result)
                    
                    new_messages.append(
                        ToolMessage(
                            content=result,
                            name=tool_call["name"],
                            tool_call_id=tool_call["id"],
                        )
                    )

                except Exception as e:
                    new_messages.append(
                        ToolMessage(
                            content=f"Error executing tool: {str(e)}",
                            name=tool_call["name"],
                            tool_call_id=tool_call["id"],
                        )
                    )

            return {"messages": new_messages}

    class GenerateMetadata:
        async def ainvoke(self, state, config=None):
            print("Generating metadata...")

            # Get the IPFS URI from the previous message
            ipfs_uri = None
            for message in reversed(state["messages"]):
                if (
                    isinstance(message, ToolMessage)
                    and message.name == "upload_image_to_ipfs"
                ):
                    if "Successfully uploaded image to IPFS:" in message.content:
                        ipfs_uri = message.content.split(
                            "Successfully uploaded image to IPFS: "
                        )[1].strip()
                        break

            if not ipfs_uri:
                return {
                    "messages": [
                        AIMessage(
                            content="Failed to extract IPFS URI from upload result."
                        )
                    ]
                }

            # Get the original image description from earlier messages
            original_description = ""
            for message in state["messages"]:
                if isinstance(message, HumanMessage) and "Generate" in message.content:
                    original_description = message.content
                    break

            # Use a simple LLM without tools for metadata generation
            metadata_llm = ChatOpenAI(model="gpt-4o-mini")

            # Create a prompt for the LLM to generate metadata in the exact format we need
            metadata_prompt = HumanMessage(
                content=f"""I've uploaded an image to IPFS with URI: {ipfs_uri}. 
                    The image was created based on this description: "{original_description}"

                    Please generate metadata for this IP with the following fields:
                    1. Name: A creative name for this IP
                    2. Description: A detailed description of what's in the image
                    3. Attributes: A list of traits in the exact format shown below:

                    [
                    {{"trait_type": "style", "value": "[one-word style descriptor]"}},
                    {{"trait_type": "mood", "value": "[one-word mood descriptor]"}},
                    {{"trait_type": "setting", "value": "[one-word setting descriptor]"}}
                    ]

                    Format your response exactly like this:
                    {{
                    "name": "Your creative name here",
                    "description": "Your detailed description here",
                    "attributes": [
                        {{"trait_type": "style", "value": "anime"}},
                        {{"trait_type": "mood", "value": "exciting"}},
                        {{"trait_type": "setting", "value": "mountains"}}
                    ]
                }}"""
            )

            # Get LLM to generate metadata suggestions in the correct format
            metadata_response = await metadata_llm.ainvoke([metadata_prompt])

            # Store the IPFS URI in the message for the next node
            return {
                "messages": [
                    AIMessage(
                        content=f"IPFS_URI: {ipfs_uri}\n\n{metadata_response.content}"
                    )
                ]
            }

    class CreateMetadata:
        async def ainvoke(self, state, config=None):
            print("Creating metadata...")
            new_messages = []

            # Get the metadata suggestions from the LLM
            metadata_message = None
            for message in reversed(state["messages"]):
                if isinstance(message, AIMessage) and "IPFS_URI:" in message.content:
                    metadata_message = message
                    break

            if not metadata_message:
                return {
                    "messages": [
                        AIMessage(content="Failed to find metadata suggestions.")
                    ]
                }

            # Extract IPFS URI from the message
            ipfs_uri = (
                metadata_message.content.split("IPFS_URI:")[1].split("\n")[0].strip()
            )

            # Extract the JSON part of the message
            metadata_content = metadata_message.content.split("IPFS_URI:")[1].split(
                "\n\n", 1
            )[1]

            try:
                # Try to parse the JSON directly from the LLM response
                import json
                import re

                # Look for JSON content between curly braces
                json_match = re.search(r"\{.*\}", metadata_content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    metadata_dict = json.loads(json_str)

                    name = metadata_dict.get("name", "AI Generated Artwork")
                    description = metadata_dict.get(
                        "description", "An AI-generated artwork uploaded to IPFS"
                    )
                    attributes = metadata_dict.get("attributes", [])

                    # Validate attributes format
                    valid_attributes = []
                    for attr in attributes:
                        if (
                            isinstance(attr, dict)
                            and "trait_type" in attr
                            and "value" in attr
                        ):
                            valid_attributes.append(attr)

                    # If no valid attributes found, create some default ones
                    if not valid_attributes:
                        valid_attributes = [
                            {"trait_type": "style", "value": "digital"},
                            {"trait_type": "creator", "value": "AI"},
                        ]
                else:
                    # Fallback to manual parsing if JSON extraction fails
                    name = "AI Generated Artwork"
                    description = "An AI-generated artwork uploaded to IPFS"

                    # Extract name if present
                    if "name" in metadata_content.lower():
                        name_match = re.search(
                            r'"name"\s*:\s*"([^"]+)"', metadata_content, re.IGNORECASE
                        )
                        if name_match:
                            name = name_match.group(1)

                    # Extract description if present
                    if "description" in metadata_content.lower():
                        desc_match = re.search(
                            r'"description"\s*:\s*"([^"]+)"',
                            metadata_content,
                            re.IGNORECASE,
                        )
                        if desc_match:
                            description = desc_match.group(1)

                    # Create default attributes
                    valid_attributes = [
                        {"trait_type": "style", "value": "digital"},
                        {"trait_type": "creator", "value": "AI"},
                    ]

                # Call the create_ip_metadata tool with properly formatted data
                result = await create_metadata_tool.ainvoke(
                    {
                        "image_uri": ipfs_uri,
                        "name": name,
                        "description": description,
                        "attributes": valid_attributes,
                    }
                )
                
                new_messages.append(
                    ToolMessage(
                        content=result,
                        name="create_ip_metadata",
                        tool_call_id=str(uuid.uuid4()),
                    )
                )

            except Exception as e:
                new_messages.append(
                    ToolMessage(
                        content=f"Error creating metadata: {str(e)}",
                        name="create_ip_metadata",
                        tool_call_id=str(uuid.uuid4()),
                    )
                )

            return {"messages": new_messages}

    class NegotiateTerms:
        async def ainvoke(self, state, config=None):
            # Check if this is the first negotiation or a subsequent one
            is_first_negotiation = True
            for message in state["messages"]:
                if (
                    isinstance(message, AIMessage)
                    and "Terms have been set for this IP:" in message.content
                ):
                    is_first_negotiation = False
                    break

            if is_first_negotiation:
                print("Negotiating terms...")
            else:
                print("Deliberating...")

            # Get the registration metadata from the previous message
            registration_metadata = None
            for message in reversed(state["messages"]):
                if (
                    isinstance(message, ToolMessage)
                    and message.name == "create_ip_metadata"
                ):
                    if "Registration metadata for minting:" in message.content:
                        metadata_section = message.content.split(
                            "Registration metadata for minting:"
                        )[1].strip()

                        try:
                            registration_metadata = json.loads(metadata_section)
                            break
                        except json.JSONDecodeError:
                            pass

            if not registration_metadata:
                return {
                    "messages": [
                        AIMessage(
                            content="Failed to extract registration metadata from previous steps."
                        )
                    ]
                }

            # Get the original image description for context
            original_description = ""
            for message in state["messages"]:
                if isinstance(message, HumanMessage) and "Generate" in message.content:
                    original_description = message.content
                    break

            # Create a prompt for negotiation
            negotiation_prompt = """
                You are a helpful IP licensing assistant. You need to negotiate fair terms for this digital artwork.

                For commercial revenue share:
                - Range is 0-100%
                - 0% means the creator gets no revenue from commercial use
                - 100% means the creator gets all revenue from commercial use
                - Typical range is 5-20% for most digital art
                - Higher quality, unique art can command 15-30%
                - Consider the uniqueness and quality of the artwork

                For derivatives allowed:
                - This is a yes/no decision
                - If yes, others can create derivative works
                - If no, the artwork cannot be modified
                - Most digital art allows derivatives with proper attribution
                - Consider if the artwork has unique elements worth protecting

                Your goal is to help the user understand these terms and reach a fair agreement.
                Start by explaining these options and suggesting reasonable defaults based on the artwork.
                DO NOT use markdown formatting in your response.
                Keep your explanation concise and user-friendly.
            """

            # First message to explain terms and suggest defaults
            initial_message = HumanMessage(
                content=f"""
                    The following artwork has been created and uploaded to IPFS:
                    Description: {original_description}

                    We need to set terms for this IP before minting:

                    1. Commercial Revenue Share: What percentage of revenue should the creator receive when this IP is used commercially?
                    2. Derivatives Allowed: Should others be allowed to create derivative works based on this IP?

                    Please explain these options to the user and suggest reasonable defaults.
                """
            )

            # Get initial explanation from the LLM
            explanation = await simple_model.ainvoke(
                [SystemMessage(content=negotiation_prompt), initial_message]
            )

            # Ask the user for their preferences
            human_review = interrupt(
                {
                    "question": "Please set the terms for your IP",
                    "explanation": explanation.content,
                    "fields": [
                        {
                            "name": "commercial_rev_share",
                            "type": "slider",
                            "min": 0,
                            "max": 100,
                            "default": 15,
                            "label": "Commercial Revenue Share (%)",
                        },
                        {
                            "name": "derivatives_allowed",
                            "type": "boolean",
                            "default": True,
                            "label": "Allow Derivative Works",
                        },
                    ],
                }
            )

            # Get the user's choices
            commercial_rev_share = human_review.get("commercial_rev_share", 15)
            derivatives_allowed = human_review.get("derivatives_allowed", True)

            # Validate the commercial_rev_share is within bounds
            if (
                not isinstance(commercial_rev_share, (int, float))
                or commercial_rev_share < 0
                or commercial_rev_share > 100
            ):
                commercial_rev_share = 15  # Default to 15% if invalid

            # Prepare a message for the LLM to evaluate the user's choices
            evaluation_message = HumanMessage(
                content=f"""
                    The user has selected the following terms for their digital artwork:
                    - Commercial Revenue Share: {commercial_rev_share}%
                    - Derivatives Allowed: {"Yes" if derivatives_allowed else "No"}

                    Original artwork description: {original_description}

                    Are these terms reasonable? If not, please provide specific feedback on why they might not be optimal 
                    and what you would recommend instead. Be honest but tactful.

                    For commercial revenue share:
                    - If it's very low (0-5%), suggest they might be undervaluing their work
                    - If it's very high (>50%), explain that this might discourage commercial use
                    - If it's extremely high (>80%), strongly advise that this could prevent any commercial adoption

                    For derivatives:
                    - If they've disallowed derivatives, explain the potential benefits of allowing them
                    - If they've allowed derivatives but the artwork is highly unique, mention they might want to consider restrictions

                    Only suggest changes if the terms are significantly outside reasonable ranges.
                    DO NOT use markdown formatting in your response.
                """
            )

            # Get evaluation from the LLM
            evaluation = await simple_model.ainvoke(
                [SystemMessage(content=negotiation_prompt), evaluation_message]
            )

            # Check if the LLM suggests changes - only if terms are outside reasonable ranges
            suggests_changes = False

            # For commercial revenue share, only suggest changes if outside 5-30% range
            if commercial_rev_share < 5 or commercial_rev_share > 50:
                suggests_changes = True

            # If the terms are reasonable, skip the feedback step
            if not suggests_changes:
                # Store the negotiated terms and registration metadata for the next node
                return {
                    "messages": [
                        AIMessage(
                            content=f"""
                            Terms have been set for this IP:
                            - Commercial Revenue Share: {commercial_rev_share}%
                            - Derivatives Allowed: {"Yes" if derivatives_allowed else "No"}

                            Registration metadata is ready for minting.
                        """,
                            additional_kwargs={
                                "terms_data": {
                                    "commercial_rev_share": commercial_rev_share,
                                    "derivatives_allowed": derivatives_allowed,
                                    "registration_metadata": registration_metadata,
                                }
                            },
                        )
                    ]
                }

            # Only ask for feedback if the terms are outside reasonable ranges
            feedback_review = interrupt(
                {
                    "question": "The AI has some feedback on your chosen terms",
                    "explanation": evaluation.content,
                    "fields": [
                        {
                            "name": "adjust_terms",
                            "type": "boolean",
                            "default": True,
                            "label": "Would you like to adjust your terms?",
                        }
                    ],
                }
            )

            if feedback_review.get("adjust_terms", True):
                # Ask for new terms
                print("Deliberating...")
                new_terms_review = interrupt(
                    {
                        "question": "Please adjust your terms",
                        "explanation": "Based on the feedback, you can modify your terms below:",
                        "fields": [
                            {
                                "name": "commercial_rev_share",
                                "type": "slider",
                                "min": 0,
                                "max": 100,
                                "default": commercial_rev_share,
                                "label": "Commercial Revenue Share (%)",
                            },
                            {
                                "name": "derivatives_allowed",
                                "type": "boolean",
                                "default": derivatives_allowed,
                                "label": "Allow Derivative Works",
                            },
                        ],
                    }
                )

                # Update with new terms
                commercial_rev_share = new_terms_review.get(
                    "commercial_rev_share", commercial_rev_share
                )
                derivatives_allowed = new_terms_review.get(
                    "derivatives_allowed", derivatives_allowed
                )

                # Validate again
                if (
                    not isinstance(commercial_rev_share, (int, float))
                    or commercial_rev_share < 0
                    or commercial_rev_share > 100
                ):
                    commercial_rev_share = 15  # Default to 15% if invalid

            # Store the negotiated terms and registration metadata for the next node
            return {
                "messages": [
                    AIMessage(
                        content=f"""
                            Terms have been set for this IP:
                            - Commercial Revenue Share: {commercial_rev_share}%
                            - Derivatives Allowed: {"Yes" if derivatives_allowed else "No"}

                            Registration metadata is ready for minting.
                    """,
                        additional_kwargs={
                            "terms_data": {
                                "commercial_rev_share": commercial_rev_share,
                                "derivatives_allowed": derivatives_allowed,
                                "registration_metadata": registration_metadata,
                            }
                        },
                    )
                ]
            }

    class MintRegisterIP:
        async def ainvoke(self, state, config=None):
            print("Minting and registering IP...")

            # Get the terms data from the previous message
            terms_data = None
            for message in reversed(state["messages"]):
                if (
                    isinstance(message, AIMessage)
                    and hasattr(message, "additional_kwargs")
                    and "terms_data" in message.additional_kwargs
                ):
                    terms_data = message.additional_kwargs["terms_data"]
                    break

            if not terms_data:
                return {
                    "messages": [
                        AIMessage(
                            content="Failed to extract terms data from previous steps."
                        )
                    ]
                }

            try:
                # Extract the parameters
                commercial_rev_share = terms_data["commercial_rev_share"]
                derivatives_allowed = terms_data["derivatives_allowed"]
                registration_metadata = terms_data["registration_metadata"]
                
                # Fix the metadata format - ensure hashes have 0x prefix
                fixed_metadata = {}
                if registration_metadata:
                    fixed_metadata = {
                        "ip_metadata_uri": registration_metadata.get("ip_metadata_uri", ""),
                        "ip_metadata_hash": registration_metadata.get("ip_metadata_hash", ""),
                        "nft_metadata_uri": registration_metadata.get("nft_metadata_uri", ""),
                        "nft_metadata_hash": registration_metadata.get("nft_metadata_hash", "")
                    }
                    
                    # Add 0x prefix to hashes if missing
                    if "ip_metadata_hash" in fixed_metadata and not fixed_metadata["ip_metadata_hash"].startswith("0x"):
                        fixed_metadata["ip_metadata_hash"] = "0x" + fixed_metadata["ip_metadata_hash"]
                    
                    if "nft_metadata_hash" in fixed_metadata and not fixed_metadata["nft_metadata_hash"].startswith("0x"):
                        fixed_metadata["nft_metadata_hash"] = "0x" + fixed_metadata["nft_metadata_hash"]

                # Convert parameters to strings as expected by the tool
                tool_args = {
                    "commercial_rev_share": str(commercial_rev_share),
                    "derivatives_allowed": str(derivatives_allowed).lower(),
                    "registration_metadata": fixed_metadata
                }

                # Call the mint_and_register_ip_with_terms tool
                result = await mint_register_ip_tool.ainvoke(tool_args)

                # Check if there was an error related to derivatives
                if (
                    "Cannot add derivative attribution when derivative use is disabled"
                    in result
                ):
                    # Retry with derivatives allowed
                    tool_args["derivatives_allowed"] = "true"
                    result = await mint_register_ip_tool.ainvoke(tool_args)
                    
                ip_id = None
                tx_hash = None
                license_terms_ids = []

                # Extract IP ID
                ip_id_match = re.search(r"IP ID: (0x[a-fA-F0-9]+)", result)
                if ip_id_match:
                    ip_id = ip_id_match.group(1)
                    # Print the IP link in the requested format
                    print(f"\n@https://aeneid.explorer.story.foundation/ipa/{ip_id}")

                # Extract Transaction Hash
                tx_hash_match = re.search(r"Transaction Hash: ([a-fA-F0-9]+)", result)
                if tx_hash_match:
                    tx_hash = tx_hash_match.group(1)
                    # Print the transaction link in the requested format
                    print(f"@https://aeneid.storyscan.xyz/tx/0x{tx_hash}")

                # Extract License Terms IDs
                license_terms_match = re.search(r"License Terms IDs: \[(.*?)\]", result)
                if license_terms_match:
                    terms_str = license_terms_match.group(1)
                    # Parse the comma-separated list
                    if terms_str:
                        license_terms_ids = [
                            int(term.strip())
                            for term in terms_str.split(",")
                            if term.strip().isdigit()
                        ]

                # If we still don't have an IP ID, the minting failed
                if not ip_id:
                    # Try one more time with more reasonable defaults and fixed metadata format
                    tool_args = {
                        "commercial_rev_share": "15",
                        "derivatives_allowed": "true",
                        "registration_metadata": fixed_metadata
                    }
                    
                    print(f"\n--- Final Retry Arguments ---")
                    print(json.dumps(tool_args, indent=2))
                    print("----------------------------\n")
                    
                    result = await mint_register_ip_tool.ainvoke(tool_args)
                    
                    # Extract IP ID again
                    ip_id_match = re.search(r"IP ID: (0x[a-fA-F0-9]+)", result)
                    if ip_id_match:
                        ip_id = ip_id_match.group(1)
                        # Print the IP link in the requested format
                        print(
                            f"\n@https://aeneid.explorer.story.foundation/ipa/{ip_id}"
                        )

                    # Extract Transaction Hash again
                    tx_hash_match = re.search(
                        r"Transaction Hash: ([a-fA-F0-9]+)", result
                    )
                    if tx_hash_match:
                        tx_hash = tx_hash_match.group(1)
                        # Print the transaction link in the requested format
                        print(f"@https://aeneid.storyscan.xyz/tx/0x{tx_hash}")

                    # Extract License Terms IDs again
                    license_terms_match = re.search(
                        r"License Terms IDs: \[(.*?)\]", result
                    )
                    if license_terms_match:
                        terms_str = license_terms_match.group(1)
                        if terms_str:
                            license_terms_ids = [
                                int(term.strip())
                                for term in terms_str.split(",")
                                if term.strip().isdigit()
                            ]

                return {
                    "messages": [
                        ToolMessage(
                            content=result,
                            name="mint_and_register_ip_with_terms",
                            tool_call_id=str(uuid.uuid4()),
                            additional_kwargs={
                                "minting_data": {
                                    "ip_id": ip_id,
                                    "license_terms_ids": license_terms_ids,
                                    "tx_hash": tx_hash,
                                }
                            },
                        )
                    ]
                }

            except Exception as e:
                import traceback
                print(f"\n--- Exception in MintRegisterIP ---")
                print(traceback.format_exc())
                print("----------------------------\n")
                
                return {
                    "messages": [
                        ToolMessage(
                            content=f"Error minting and registering IP: {str(e)}",
                            name="mint_and_register_ip_with_terms",
                            tool_call_id=str(uuid.uuid4()),
                        )
                    ]
                }

    class MintLicenseTokens:
        async def ainvoke(self, state, config=None):
            print("Minting license tokens...")

            # Get the minting data from the previous message
            minting_data = None
            for message in reversed(state["messages"]):
                if hasattr(message, "additional_kwargs") and "minting_data" in message.additional_kwargs:
                    minting_data = message.additional_kwargs["minting_data"]
                    break

            if not minting_data:
                return {
                    "messages": [
                        ToolMessage(
                            content="Error: No minting data found for license tokens.",
                            name="mint_license_tokens",
                            tool_call_id=str(uuid.uuid4()),
                        )
                    ]
                }

            try:
                # Simulate minting license tokens
                # In a real implementation, this would call the Story Protocol SDK
                import time
                import random

                time.sleep(2)  # Simulate blockchain transaction time

                # Generate a random transaction hash
                tx_hash = "0x" + "".join(
                    random.choice("0123456789abcdef") for _ in range(64)
                )
                
                # Generate random license token IDs
                license_token_ids = [random.randint(10000, 99999) for _ in range(3)]

                # Store the license token data
                license_data = {
                    "tx_hash": tx_hash,
                    "license_token_ids": license_token_ids,
                    "ip_id": minting_data.get("ip_id"),
                    "terms": minting_data.get("terms")
                }

                return {
                    "messages": [
                        ToolMessage(
                            content=f"Successfully minted license tokens with IDs: {', '.join(map(str, license_token_ids))}. Transaction hash: {tx_hash}",
                            name="mint_license_tokens",
                            tool_call_id=str(uuid.uuid4()),
                            additional_kwargs={"license_data": license_data, "minting_data": minting_data}
                        )
                    ]
                }
            except Exception as e:
                return {
                    "messages": [
                        ToolMessage(
                            content=f"Error minting license tokens: {str(e)}",
                            name="mint_license_tokens",
                            tool_call_id=str(uuid.uuid4()),
                        )
                    ]
                }

    class PostToTwitter:
        """Post to Twitter about the minted IP asset."""

        async def ainvoke(self, state, config=None):
            print("Posting to Twitter about the minted IP asset...")
            
            # Extract image URL from the messages
            image_url = None
            ip_id = None
            tx_hash = None

            # First find the image URL
            for message in state["messages"]:
                if hasattr(message, "content") and isinstance(message.content, str):
                    if "https://" in message.content and (".png" in message.content or ".jpg" in message.content or ".jpeg" in message.content):
                        # Extract URL from the message
                        words = message.content.split()
                        for word in words:
                            if word.startswith("https://") and (".png" in word or ".jpg" in word or ".jpeg" in word):
                                image_url = word.strip(",.()[]{}\"'")
                                break
                    if image_url:
                        break

            # Extract minting data from the most recent messages
            for message in reversed(state["messages"]):
                if hasattr(message, "additional_kwargs") and "minting_data" in message.additional_kwargs:
                    minting_data = message.additional_kwargs["minting_data"]
                    ip_id = minting_data.get("ip_id")
                    tx_hash = minting_data.get("tx_hash")
                    break

            if ip_id and tx_hash:
                try:
                    print(f"\nPosting to Twitter about minted IP asset (ID: {ip_id})...")
                    # Post to Twitter
                    response = await post_ip_minted_tweet(ip_id, tx_hash, image_url)
                    
                    if response["success"]:
                        result = f"Successfully posted to Twitter about the minted IP asset (ID: {ip_id})."
                        print(f"\n✅ {result}")
                    else:
                        result = f"Failed to post to Twitter: {response.get('error', 'Unknown error')}"
                        print(f"\n❌ {result}")
                except Exception as e:
                    import traceback
                    print(f"\n--- Exception in PostToTwitter ---")
                    print(traceback.format_exc())
                    print("----------------------------\n")
                    result = f"Error posting to Twitter: {str(e)}"
                    print(f"\n❌ {result}")
            else:
                result = "Could not post to Twitter: Missing IP ID or transaction hash."
                print(f"\n❌ {result}")

            return {
                "messages": [
                    ToolMessage(
                        content=result,
                        name="post_to_twitter",
                        tool_call_id=str(uuid.uuid4()),
                    )
                ]
            }

    class HumanReviewNode:
        async def ainvoke(self, state, config=None):
            last_message = state["messages"][-1]

            # Initialize content variables
            content_url = None
            content_type = "image"  # Default to image
            local_file_path = None

            # Check for DALL-E generated image
            if "Generated image URL:" in last_message.content:
                content_url = last_message.content.split("Generated image URL: ")[1].strip()
            
            # Check for Luma generated video
            elif "Generated video URL:" in last_message.content:
                content_url = last_message.content.split("Generated video URL: ")[1].strip()
                content_type = "video"
            
            # Check for local file upload
            elif "File path:" in last_message.content:
                local_file_path = last_message.content.split("File path: ")[1].strip()
                
                # Determine content type from file extension
                if local_file_path.lower().endswith(('.mp4', '.mov', '.avi', '.webm')):
                    content_type = "video"
                else:
                    content_type = "image"
                
                return {
                    "messages": [
                        AIMessage(
                            content=f"Uploading local {content_type} file to IPFS: {local_file_path}",
                            tool_calls=[
                                {
                                    "id": str(uuid.uuid4()),
                                    "name": "upload_image_to_ipfs",
                                    "args": {"image_data": f"file://{local_file_path}"},
                                }
                            ],
                        )
                    ],
                    "next": "run_ipfs_tool",
                }
            
            # Check for URLs in the content
            else:
                for line in last_message.content.split('\n'):
                    if line.startswith("http"):
                        # Extract URL from the message
                        words = line.split()
                        for word in words:
                            if word.startswith("http"):
                                # Determine content type from URL extension
                                if any(ext in word.lower() for ext in ['.mp4', '.mov', '.avi', '.webm']):
                                    content_type = "video"
                                content_url = word.strip(",.()[]{}\"'")
                                break

            # If no content URL is found
            if not content_url and not local_file_path:
                return {
                    "messages": [
                        HumanMessage(
                            content="I couldn't find an image or video to review. Please try again."
                        )
                    ],
                    "next": "call_llm",
                }

            # Present content for human review
            human_review = interrupt(
                {
                    "question": f"Is this {content_type} what you wanted?", 
                    "image_url" if content_type == "image" else "video_url": content_url
                }
            )

            if human_review.get("action") == "continue":
                # If approved, create a tool call to upload to IPFS
                return {
                    "messages": [
                        AIMessage(
                            content=f"Uploading approved {content_type} to IPFS",
                            tool_calls=[
                                {
                                    "id": str(uuid.uuid4()),
                                    "name": "upload_image_to_ipfs",
                                    "args": {"image_data": content_url},
                                }
                            ],
                        )
                    ],
                    "next": "run_ipfs_tool",
                }
            else:
                # If rejected, send feedback to LLM to regenerate
                return {
                    "messages": [
                        HumanMessage(
                            content=f"I don't like that {content_type}. {human_review.get('data', f'Please generate a different {content_type}.')}"
                        )
                    ],
                    "next": "call_llm",
                }

    class HandleFailedGeneration:
        async def ainvoke(self, state, config=None):
            # Get the original prompt from the human message
            original_prompt = ""
            for message in state["messages"]:
                if isinstance(message, HumanMessage) and "Generate" in message.content:
                    original_prompt = message.content.replace("Generate ", "")
                    break
        
            print(f"\nUnable to generate image of {original_prompt}")
            new_prompt = input("Please try a different prompt: ")
        
            return {
                "messages": [
                    SystemMessage(content="""You are an assistant that helps users create and mint IP assets on Story Protocol.
Your goal is to guide the user through the process of:
1. Generating an image based on their prompt
2. Uploading the image to IPFS
3. Creating metadata for the IP asset
4. Negotiating terms for the IP asset
5. Minting and registering the IP asset
6. Minting license tokens
7. Posting about the minted IP asset on Twitter

Use the available tools to accomplish these tasks. When generating images, use the generate_image tool.
"""),
                    HumanMessage(content=f"Generate {new_prompt}")
                ],
                "next": "call_llm"  # Go back to the LLM with the new prompt
            }

    workflow = StateGraph(State)

    workflow.add_node("call_llm", RunnableLambda(CallLLM().ainvoke))
    workflow.add_node("run_tool", RunnableLambda(RunTool().ainvoke))
    workflow.add_node("run_ipfs_tool", RunnableLambda(RunIPFSTool().ainvoke))
    workflow.add_node("human_review_node", RunnableLambda(HumanReviewNode().ainvoke))
    workflow.add_node("generate_metadata", RunnableLambda(GenerateMetadata().ainvoke))
    workflow.add_node("create_metadata", RunnableLambda(CreateMetadata().ainvoke))
    workflow.add_node("negotiate_terms", RunnableLambda(NegotiateTerms().ainvoke))
    workflow.add_node("mint_register_ip", RunnableLambda(MintRegisterIP().ainvoke))
    workflow.add_node(
        "mint_license_tokens", RunnableLambda(MintLicenseTokens().ainvoke)
    )
    workflow.add_node("post_to_twitter", RunnableLambda(PostToTwitter().ainvoke))
    workflow.add_node("handle_failed_generation", RunnableLambda(HandleFailedGeneration().ainvoke))

    # Start -> call LLM to generate image
    workflow.add_edge(START, "call_llm")

    # LLM -> run tool (for image generation)
    workflow.add_edge("call_llm", "run_tool")

    # Run tool -> human review (only for image generation)
    workflow.add_conditional_edges(
        "run_tool",
        lambda x: x.get("next", 
            "human_review_node" 
            if (
                x["messages"]
                and isinstance(x["messages"][-1], ToolMessage)
                and x["messages"][-1].name in ["generate_image", "generate_luma_video", "upload_local_file"]
                and (
                    "Generated image URL:" in x["messages"][-1].content
                    or "Generated video URL:" in x["messages"][-1].content
                    or "File path:" in x["messages"][-1].content
                )
            )
            else "handle_failed_generation" if (
                x["messages"]
                and isinstance(x["messages"][-1], ToolMessage)
                and x["messages"][-1].name in ["generate_image", "generate_luma_video", "upload_local_file"]
                and "Error:" in x["messages"][-1].content
            )
            else "call_llm"
        )
    )

    # Human review -> either run IPFS tool or call LLM again based on response
    workflow.add_conditional_edges(
        "human_review_node",
        lambda x: x.get("next"),  # This will be either "run_ipfs_tool" or "call_llm"
    )

    # IPFS tool -> generate metadata
    workflow.add_edge("run_ipfs_tool", "generate_metadata")

    # Generate metadata -> create metadata
    workflow.add_edge("generate_metadata", "create_metadata")

    # Create metadata -> negotiate terms
    workflow.add_edge("create_metadata", "negotiate_terms")

    # Negotiate terms -> mint and register IP
    workflow.add_edge("negotiate_terms", "mint_register_ip")

    # Mint and register IP -> mint license tokens
    workflow.add_edge("mint_register_ip", "mint_license_tokens")

    # Mint license tokens -> post to Twitter
    workflow.add_edge("mint_license_tokens", "post_to_twitter")

    # Post to Twitter -> END
    workflow.add_edge("post_to_twitter", END)

    # Add memory to graph compilation
    memory = MemorySaver()

    # Add memory to graph compilation
    graph = workflow.compile(checkpointer=memory)

    # Save visualization
    mermaid_png = graph.get_graph().draw_mermaid_png()
    with open("workflow_graph.png", "wb") as f:
        f.write(mermaid_png)

    return graph


async def run_agent():
    # Create the MCP client and keep it open for the entire session
    async with MultiServerMCPClient() as client:
        # Connect to the server
        await client.connect_to_server(
            "story_server",
            command="python",
            args=["../story-sdk-mcp/server.py"],
        )
        # Get all required tools
        ipfs_tools = [
            tool
            for tool in client.get_tools()
            if tool.name
            in [
                "upload_image_to_ipfs",
                "create_ip_metadata",
                "mint_and_register_ip_with_terms",
                "mint_license_tokens",
            ]
        ]

        # Create the graph with the tools
        graph = create_graph(ipfs_tools)

        thread_id = str(uuid.uuid4())

        # Prompt the user for what image they want to create
        print("\n=== Story IP Creator ===")
        print(
            "This tool will help you create and mint an image or video as an IP asset in the Story ecosystem.\n"
        )

        # Present asset creation options
        print("Please select an option for creating your IP asset:")
        print("1. Upload a local image or video file")
        print("2. Generate an image using OpenAI DALL-E")
        print("3. Generate a video using Luma API")
        
        # Get user choice
        while True:
            try:
                choice = int(input("\nEnter your choice (1-3): "))
                if 1 <= choice <= 3:
                    break
                print("Please enter a number between 1 and 3.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Handle user choice
        if choice == 1:
            # Local file upload
            file_path = input("\nEnter the path to your image or video file: ")
            initial_input = {
                "messages": [
                    SystemMessage(content="""You are an assistant that helps users create and mint IP assets on Story Protocol.
Your goal is to guide the user through the process of:
1. Uploading a local file
2. Uploading the file to IPFS
3. Creating metadata for the IP asset
4. Negotiating terms for the IP asset
5. Minting and registering the IP asset
6. Minting license tokens
7. Posting about the minted IP asset on Twitter

Use the available tools to accomplish these tasks. When uploading files, use the upload_local_file tool.
"""),
                    HumanMessage(content=f"Upload this file: {file_path}")
                ]
            }
            print("\nStarting the upload process...\n")
            
        elif choice == 2:
            # OpenAI image generation
            image_prompt = input(
                "\nWhat image would you like to create? (e.g., 'an anime style image of a person snowboarding'): "
            )
            if not image_prompt:
                image_prompt = (
                    "an anime style image of a person snowboarding"  # Default if empty
                )
                print(f"Using default prompt: '{image_prompt}'")

            initial_input = {
                "messages": [
                    SystemMessage(content="""You are an assistant that helps users create and mint IP assets on Story Protocol.
Your goal is to guide the user through the process of:
1. Generating an image based on their prompt
2. Uploading the image to IPFS
3. Creating metadata for the IP asset
4. Negotiating terms for the IP asset
5. Minting and registering the IP asset
6. Minting license tokens
7. Posting about the minted IP asset on Twitter

Use the available tools to accomplish these tasks. When generating images, use the generate_image tool.
"""),
                    HumanMessage(content=f"Generate {image_prompt}")
                ]
            }
            print("\nStarting the image generation process...\n")
            
        elif choice == 3:
            # Luma video generation
            video_prompt = input(
                "\nWhat video would you like to create? (e.g., 'a short clip of a sunset over mountains'): "
            )
            if not video_prompt:
                video_prompt = (
                    "a short clip of a sunset over mountains"  # Default if empty
                )
                print(f"Using default prompt: '{video_prompt}'")

            initial_input = {
                "messages": [
                    SystemMessage(content="""You are an assistant that helps users create and mint IP assets on Story Protocol.
Your goal is to guide the user through the process of:
1. Generating a video based on their prompt
2. Uploading the video to IPFS
3. Creating metadata for the IP asset
4. Negotiating terms for the IP asset
5. Minting and registering the IP asset
6. Minting license tokens
7. Posting about the minted IP asset on Twitter

Use the available tools to accomplish these tasks. When generating videos, use the generate_luma_video tool.
"""),
                    HumanMessage(content=f"Generate video: {video_prompt}")
                ]
            }
            print("\nStarting the video generation process...\n")

        # Add thread_id to the config
        config = {"configurable": {"thread_id": thread_id}}

        # Process all events and handle interrupts at any stage
        async def process_events(input_data):
            async for event in graph.astream(input_data, config, stream_mode="updates"):
                # Only process interrupts
                if "__interrupt__" in event:
                    interrupt_data = event["__interrupt__"][0].value

                    # Check which type of interrupt we're dealing with
                    if "image_url" in interrupt_data:
                        # This is the image review interrupt
                        # Display the image URL once so the user can see what was generated
                        print(f"\nGenerated image: {interrupt_data['image_url']}\n")

                        user_input = input(
                            "Do you like this image? (yes/no + feedback): "
                        )

                        if user_input.lower().startswith("yes"):
                            # Continue to IPFS upload
                            print("Uploading image to IPFS...")
                            await process_events(Command(resume={"action": "continue"}))
                        else:
                            # Get feedback after "no"
                            feedback = (
                                user_input[4:]
                                if len(user_input) > 4
                                else "Please generate a different image"
                            )
                            print("Generating a new image...")
                            await process_events(
                                Command(resume={"action": "feedback", "data": feedback})
                            )

                    elif "fields" in interrupt_data:
                        # Check if this is the terms negotiation interrupt
                        if "commercial_rev_share" in [
                            field["name"] for field in interrupt_data.get("fields", [])
                        ]:
                            # This is the initial terms negotiation interrupt
                            print("\n" + interrupt_data.get("explanation", ""))

                            # Get commercial revenue share
                            while True:
                                try:
                                    rev_share = int(
                                        input(
                                            "Enter Commercial Revenue Share (0-100%, default: 15%): "
                                        )
                                        or "15"
                                    )
                                    if 0 <= rev_share <= 100:
                                        break
                                    print("Please enter a value between 0 and 100.")
                                except ValueError:
                                    print("Please enter a valid number.")

                            # Get derivatives allowed
                            while True:
                                deriv_input = (
                                    input(
                                        "Allow Derivative Works? (yes/no, default: yes): "
                                    ).lower()
                                    or "yes"
                                )
                                if deriv_input in ["yes", "no", "y", "n"]:
                                    derivatives_allowed = deriv_input.startswith("y")
                                    break
                                print("Please enter yes or no.")

                            # Resume with the user's choices
                            await process_events(
                                Command(
                                    resume={
                                        "commercial_rev_share": rev_share,
                                        "derivatives_allowed": derivatives_allowed,
                                    }
                                )
                            )

                        # Check if this is the feedback on terms interrupt
                        elif "adjust_terms" in [
                            field["name"] for field in interrupt_data.get("fields", [])
                        ]:
                            # This is the feedback on terms interrupt
                            print("\n" + interrupt_data.get("explanation", ""))

                            # Ask if user wants to adjust terms
                            while True:
                                adjust_input = input(
                                    "Would you like to adjust your terms based on this feedback? (yes/no, default: yes): "
                                ).lower() or ("yes" if interrupt_data.get("default", True) else "no")
                                if adjust_input in [
                                    "yes",
                                    "no",
                                    "y",
                                    "n",
                                    "",
                                ]:  # Empty string for default
                                    adjust_terms = not (
                                        adjust_input.startswith("n")
                                    )  # Default to yes
                                    break
                                print("Please enter yes or no.")

                            # Resume with the user's choice
                            await process_events(
                                Command(resume={"adjust_terms": adjust_terms})
                            )

                        # Check if this is the term adjustment interrupt
                        elif (
                            len(interrupt_data.get("fields", [])) == 2
                            and "commercial_rev_share"
                            in [
                                field["name"]
                                for field in interrupt_data.get("fields", [])
                            ]
                            and "derivatives_allowed"
                            in [
                                field["name"]
                                for field in interrupt_data.get("fields", [])
                            ]
                        ):
                            # This is the term adjustment interrupt
                            print("\n" + interrupt_data.get("explanation", ""))

                            # Get commercial revenue share
                            while True:
                                try:
                                    rev_share = int(
                                        input(
                                            f"Enter Commercial Revenue Share (0-100%, default: {interrupt_data['fields'][0].get('default', 15)}%): "
                                        )
                                        or str(
                                            interrupt_data["fields"][0].get(
                                                "default", 15
                                            )
                                        )
                                    )
                                    if 0 <= rev_share <= 100:
                                        break
                                    print("Please enter a value between 0 and 100.")
                                except ValueError:
                                    print("Please enter a valid number.")

                            # Get derivatives allowed
                            while True:
                                default_deriv = (
                                    "yes"
                                    if interrupt_data["fields"][1].get("default", True)
                                    else "no"
                                )
                                deriv_input = (
                                    input(
                                        f"Allow Derivative Works? (yes/no, default: {default_deriv}): "
                                    ).lower()
                                    or default_deriv
                                )
                                if deriv_input in ["yes", "no", "y", "n"]:
                                    derivatives_allowed = deriv_input.startswith("y")
                                    break
                                print("Please enter yes or no.")

                            # Resume with the user's choices
                            await process_events(
                                Command(
                                    resume={
                                        "commercial_rev_share": rev_share,
                                        "derivatives_allowed": derivatives_allowed,
                                    }
                                )
                            )

                        else:
                            # Generic fields handler
                            print("Please provide the requested information:")
                            responses = {}

                            for field in interrupt_data.get("fields", []):
                                field_name = field.get("name", "")
                                field_type = field.get("type", "text")
                                field_default = field.get("default", "")
                                field_label = field.get("label", field_name)

                                if field_type == "boolean":
                                    while True:
                                        value_input = input(
                                            f"{field_label}? (yes/no, default: {'yes' if field_default else 'no'}): "
                                        ).lower() or ("yes" if field_default else "no")
                                        if value_input in ["yes", "no", "y", "n"]:
                                            responses[field_name] = (
                                                value_input.startswith("y")
                                            )
                                            break
                                        print("Please enter yes or no.")

                                elif field_type == "slider":
                                    min_val = field.get("min", 0)
                                    max_val = field.get("max", 100)
                                    while True:
                                        try:
                                            value_input = input(
                                                f"{field_label} ({min_val}-{max_val}, default: {field_default}): "
                                            ) or str(field_default)
                                            value = int(value_input)
                                            if min_val <= value <= max_val:
                                                responses[field_name] = value
                                                break
                                            print(
                                                f"Please enter a value between {min_val} and {max_val}."
                                            )
                                        except ValueError:
                                            print("Please enter a valid number.")

                                else:  # text or other types
                                    value_input = input(
                                        f"{field_label} (default: {field_default}): "
                                    ) or str(field_default)
                                    responses[field_name] = value_input

                            # Resume with all responses
                            await process_events(Command(resume=responses))

                    else:
                        # Generic interrupt handler for any other interrupts
                        user_input = input("Enter your response: ")
                        await process_events(Command(resume={"data": user_input}))

                # For non-interrupt events, we don't need to print anything
                # This keeps the output clean and focused on user interactions

        # Start the initial processing
        await process_events(initial_input)

        print("\n=== Process Complete ===")
        print(
            "Your IP has been successfully created and registered with Story!"
        )
        print("Thank you for using the Story IP Creation Agent.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_agent())