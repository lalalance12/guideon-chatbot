from django.db import migrations
from django.conf import settings

class Migration(migrations.Migration):
    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Enable pgvector extension if not already enabled
            CREATE EXTENSION IF NOT EXISTS vector;
            
            -- Create the AGNO memory table
            CREATE TABLE IF NOT EXISTS guideon_chat_memory (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata JSONB,
                embedding VECTOR(1024),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                summarized BOOLEAN DEFAULT FALSE
            );
            
            -- Create indexes for better performance
            CREATE INDEX IF NOT EXISTS idx_guideon_chat_memory_session_id 
                ON guideon_chat_memory (session_id);
            
            -- Create vector index for similarity search
            CREATE INDEX IF NOT EXISTS idx_guideon_chat_memory_embedding
                ON guideon_chat_memory USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            """,
            reverse_sql="""
            DROP TABLE IF EXISTS guideon_chat_memory;
            """
        ),
    ]
