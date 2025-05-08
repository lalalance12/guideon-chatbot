from typing import Dict, Any, List, Optional, Union
import json
import logging
from django.db import connection
from agno.memory import MemoryItem, BaseStorageDriver
from agno.embedder import BaseEmbedder, OpenAIEmbedder

logger = logging.getLogger(__name__)

class PostgresMemoryStorage(BaseStorageDriver):
    """
    PostgreSQL storage driver for AGNO Memory using pgvector
    
    This class handles persistent storage of memory items in PostgreSQL with vector search capability
    through pgvector extension.
    """
    
    def __init__(self, embedder: Optional[BaseEmbedder] = None):
        """
        Initialize the PostgreSQL storage driver
        
        Args:
            embedder: Optional embedder for vectorizing memory content
        """
        self.embedder = embedder or OpenAIEmbedder()
        self._ensure_tables_exist()
    
    def _ensure_tables_exist(self):
        """Create memory tables if they don't exist"""
        with connection.cursor() as cursor:
            # Check if pgvector extension is installed
            cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            if not cursor.fetchone()[0]:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
                
            # Create memories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agno_memories (
                    id SERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding VECTOR(1536),
                    metadata JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    summerized BOOLEAN DEFAULT FALSE
                );
            """)
            
            # Create index on session_id for faster filtering
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_session_id
                ON agno_memories (session_id);
            """)
            
            # Create vector index for similarity search
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_embedding
                ON agno_memories USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            """)
            
            # Create summary table for conversation summaries
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agno_summaries (
                    id SERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    start_timestamp TIMESTAMP WITH TIME ZONE,
                    end_timestamp TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
    
    def add(self, session_id: str, content: str, metadata: Dict[str, Any] = None) -> str:
        """
        Add a memory item to storage
        
        Args:
            session_id: Unique identifier for the session
            content: Text content to store
            metadata: Additional metadata for the memory item
            
        Returns:
            ID of the stored memory item
        """
        try:
            # Generate embedding for vector search
            embedding = self.embedder.embed_query(content)
            
            # Insert into database
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO agno_memories (session_id, content, embedding, metadata)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    [
                        session_id, 
                        content, 
                        embedding, 
                        json.dumps(metadata or {})
                    ]
                )
                memory_id = cursor.fetchone()[0]
                return str(memory_id)
        except Exception as e:
            logger.error(f"Error adding memory: {e}")
            # Fallback to storing without embedding if embedding fails
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO agno_memories (session_id, content, metadata)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    [
                        session_id, 
                        content, 
                        json.dumps(metadata or {})
                    ]
                )
                memory_id = cursor.fetchone()[0]
                return str(memory_id)
    
    def search(
        self, 
        session_id: str, 
        query: str = None, 
        limit: int = 10, 
        search_type: str = "semantic",
        metadata_filter: Dict[str, Any] = None
    ) -> List[MemoryItem]:
        """
        Search for memory items
        
        Args:
            session_id: Session ID to search within
            query: Search query text
            limit: Maximum number of results to return
            search_type: Type of search (semantic, last_n, first_n, agentic)
            metadata_filter: Filter by metadata fields
            
        Returns:
            List of matching memory items
        """
        if search_type == "last_n":
            # Get the most recent memories
            with connection.cursor() as cursor:
                sql = """
                    SELECT id, content, metadata, created_at
                    FROM agno_memories
                    WHERE session_id = %s
                """
                params = [session_id]
                
                # Add metadata filter if provided
                if metadata_filter:
                    for key, value in metadata_filter.items():
                        sql += f" AND metadata->>'{key}' = %s"
                        params.append(value)
                
                sql += " ORDER BY created_at DESC LIMIT %s"
                params.append(limit)
                
                cursor.execute(sql, params)
                results = cursor.fetchall()
                
                return [
                    MemoryItem(
                        id=str(row[0]),
                        content=row[1],
                        metadata=json.loads(row[2]) if row[2] else {},
                        session_id=session_id
                    )
                    for row in results
                ]
                
        elif search_type == "first_n":
            # Get the oldest memories
            with connection.cursor() as cursor:
                sql = """
                    SELECT id, content, metadata, created_at
                    FROM agno_memories
                    WHERE session_id = %s
                """
                params = [session_id]
                
                # Add metadata filter if provided
                if metadata_filter:
                    for key, value in metadata_filter.items():
                        sql += f" AND metadata->>'{key}' = %s"
                        params.append(value)
                
                sql += " ORDER BY created_at ASC LIMIT %s"
                params.append(limit)
                
                cursor.execute(sql, params)
                results = cursor.fetchall()
                
                return [
                    MemoryItem(
                        id=str(row[0]),
                        content=row[1],
                        metadata=json.loads(row[2]) if row[2] else {},
                        session_id=session_id
                    )
                    for row in results
                ]
                
        elif search_type == "semantic" and query:
            # Semantic search using vector embeddings
            try:
                query_embedding = self.embedder.embed_query(query)
                
                with connection.cursor() as cursor:
                    sql = """
                        SELECT id, content, metadata, 1 - (embedding <=> %s) as similarity
                        FROM agno_memories
                        WHERE session_id = %s
                        AND embedding IS NOT NULL
                    """
                    params = [query_embedding, session_id]
                    
                    # Add metadata filter if provided
                    if metadata_filter:
                        for key, value in metadata_filter.items():
                            sql += f" AND metadata->>'{key}' = %s"
                            params.append(value)
                    
                    sql += " ORDER BY similarity DESC LIMIT %s"
                    params.append(limit)
                    
                    cursor.execute(sql, params)
                    results = cursor.fetchall()
                    
                    return [
                        MemoryItem(
                            id=str(row[0]),
                            content=row[1],
                            metadata=json.loads(row[2]) if row[2] else {},
                            session_id=session_id
                        )
                        for row in results
                    ]
            except Exception as e:
                logger.error(f"Error in semantic search: {e}")
                # Fall back to basic text search if embedding fails
                with connection.cursor() as cursor:
                    sql = """
                        SELECT id, content, metadata
                        FROM agno_memories
                        WHERE session_id = %s
                        AND position(lower(%s) in lower(content)) > 0
                    """
                    params = [session_id, query]
                    
                    # Add metadata filter if provided
                    if metadata_filter:
                        for key, value in metadata_filter.items():
                            sql += f" AND metadata->>'{key}' = %s"
                            params.append(value)
                    
                    sql += " LIMIT %s"
                    params.append(limit)
                    
                    cursor.execute(sql, params)
                    results = cursor.fetchall()
                    
                    return [
                        MemoryItem(
                            id=str(row[0]),
                            content=row[1],
                            metadata=json.loads(row[2]) if row[2] else {},
                            session_id=session_id
                        )
                        for row in results
                    ]
        
        # Default to basic text search if no embeddings or other search type
        with connection.cursor() as cursor:
            sql = """
                SELECT id, content, metadata
                FROM agno_memories
                WHERE session_id = %s
            """
            params = [session_id]
            
            # Add query text filter if provided
            if query:
                sql += " AND position(lower(%s) in lower(content)) > 0"
                params.append(query)
                
            # Add metadata filter if provided
            if metadata_filter:
                for key, value in metadata_filter.items():
                    sql += f" AND metadata->>'{key}' = %s"
                    params.append(value)
            
            sql += " LIMIT %s"
            params.append(limit)
            
            cursor.execute(sql, params)
            results = cursor.fetchall()
            
            return [
                MemoryItem(
                    id=str(row[0]),
                    content=row[1],
                    metadata=json.loads(row[2]) if row[2] else {},
                    session_id=session_id
                )
                for row in results
            ]
    
    def delete(self, session_id: str, memory_id: str = None):
        """
        Delete memory items
        
        Args:
            session_id: Session ID to delete memories from
            memory_id: Optional specific memory ID to delete
        """
        with connection.cursor() as cursor:
            if memory_id:
                cursor.execute(
                    "DELETE FROM agno_memories WHERE session_id = %s AND id = %s",
                    [session_id, memory_id]
                )
            else:
                cursor.execute(
                    "DELETE FROM agno_memories WHERE session_id = %s",
                    [session_id]
                )
    
    def summarize_and_prune(self, session_id: str, max_items: int = 100, older_than_hours: int = 24):
        """
        Summarize old messages and prune them to prevent memory bloat
        
        Args:
            session_id: Session ID to summarize
            max_items: Maximum number of items to keep before summarizing
            older_than_hours: Summarize items older than this many hours
        """
        # First check if summarization is needed
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) 
                FROM agno_memories 
                WHERE session_id = %s AND 
                      created_at < NOW() - INTERVAL %s HOUR AND
                      summerized = FALSE
                """,
                [session_id, older_than_hours]
            )
            count = cursor.fetchone()[0]
            
            if count > max_items:
                # Get memories to summarize
                cursor.execute(
                    """
                    SELECT id, content, metadata, created_at
                    FROM agno_memories
                    WHERE session_id = %s AND 
                          created_at < NOW() - INTERVAL %s HOUR AND
                          summerized = FALSE
                    ORDER BY created_at ASC
                    """,
                    [session_id, older_than_hours]
                )
                
                memories = cursor.fetchall()
                
                if memories:
                    # Create a summary of these memories
                    memory_texts = [f"{m[1]}" for m in memories]
                    oldest_timestamp = memories[0][3]
                    newest_timestamp = memories[-1][3]
                    
                    # Simple concatenation summary for now
                    # In a production system, you'd want to use an LLM to generate a proper summary
                    summary = f"Summary of {len(memories)} messages from {oldest_timestamp} to {newest_timestamp}"
                    
                    # Store the summary
                    cursor.execute(
                        """
                        INSERT INTO agno_summaries
                        (session_id, summary, start_timestamp, end_timestamp)
                        VALUES (%s, %s, %s, %s)
                        """,
                        [session_id, summary, oldest_timestamp, newest_timestamp]
                    )
                    
                    # Mark original memories as summarized
                    memory_ids = [m[0] for m in memories]
                    placeholder = ", ".join(["%s"] * len(memory_ids))
                    cursor.execute(
                        f"UPDATE agno_memories SET summerized = TRUE WHERE id IN ({placeholder})",
                        memory_ids
                    )
                    
                    logger.info(f"Summarized {len(memories)} memories for session {session_id}")

    def get_all_sessions(self) -> List[str]:
        """Get all session IDs in storage"""
        with connection.cursor() as cursor:
            cursor.execute("SELECT DISTINCT session_id FROM agno_memories")
            return [row[0] for row in cursor.fetchall()]