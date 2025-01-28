from typing import List
import numpy as np
from models import KnowledgeBaseEntry
import os
from openai import OpenAI
from flask import current_app
import logging
from models import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_relevant_knowledge(query: str, limit: int = 3) -> List[KnowledgeBaseEntry]:
    """Find relevant knowledge base entries for the given query."""
    query_embedding = create_embedding(query)
    
    # Get all knowledge base entries and their embeddings
    entries = KnowledgeBaseEntry.query.all()
    
    # Calculate similarities
    similarities = []
    for entry in entries:
        entry_embedding = np.array(entry.embedding)
        similarity = np.dot(query_embedding, entry_embedding)
        similarities.append((similarity, entry))
    
    # Sort by similarity and return top matches
    sorted_entries = sorted(similarities, key=lambda x: x[0], reverse=True)
    return [entry for _, entry in sorted_entries[:limit]]

def create_embedding(text: str) -> np.ndarray:
    """Create an embedding for the given text using OpenAI's API."""
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    try:
        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=text
        )
        return np.array(response.data[0].embedding)
    except Exception as e:
        logger.error(f"Error creating embedding: {e}")
        raise

def update_entry_embedding(entry: KnowledgeBaseEntry) -> None:
    """Update the embedding for a knowledge base entry."""
    try:
        # Combine title and content for better context
        text = f"{entry.title}\n{entry.content}"
        embedding = create_embedding(text)
        entry.embedding = embedding.tolist()  # Convert to list for JSON storage
        db.session.commit()
    except Exception as e:
        logger.error(f"Error updating entry embedding: {e}")
        db.session.rollback()
        raise
