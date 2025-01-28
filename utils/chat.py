from typing import List, Dict
from models import Message, SenderType
from openai import OpenAI
import os
import tiktoken

def count_tokens(messages: List[Dict]) -> int:
    """Count tokens in a list of messages."""
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    num_tokens = 0
    for message in messages:
        # Every message follows {role: ..., content: ...} format
        num_tokens += 4  # Format tax per message
        for key, value in message.items():
            num_tokens += len(encoding.encode(str(value)))
    num_tokens += 2  # Every reply is primed with <im_start>assistant
    return num_tokens

def create_summary(conversation_id: int) -> str:
    """Create a summary of older messages in the conversation."""
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # Get all messages except the 10 most recent
    older_messages = Message.query.filter_by(conversation_id=conversation_id)\
        .order_by(Message.timestamp.desc())\
        .offset(10)\
        .limit(50)\
        .all()
    
    if not older_messages:
        return None
        
    # Format messages for summarization
    messages_text = "\n".join([
        f"{'Student' if msg.sender_type == SenderType.STUDENT else 'Tutor'}: {msg.message_content}"
        for msg in older_messages
    ])
    
    # Get summary from OpenAI
    summary_response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Summarize the key points of this tutoring conversation, focusing on the main concepts discussed and questions asked."},
            {"role": "user", "content": messages_text}
        ]
    )
    
    return summary_response.choices[0].message.content
