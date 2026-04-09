#!/usr/bin/env python3
"""Seed Qdrant with sample FAQ documents for the RAG pipeline."""

import asyncio
import os

from fastembed import TextEmbedding
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION = os.getenv("QDRANT_COLLECTION", "faq_documents")
EMBEDDING_MODEL = "nomic-ai/nomic-embed-text-v1"
VECTOR_DIM = 768

FAQ_DOCS = [
    {
        "source": "faq/returns",
        "text": (
            "Our return policy allows returns within 30 days of purchase. "
            "Items must be in original condition with tags attached. "
            "Refunds are processed within 5-7 business days."
        ),
    },
    {
        "source": "faq/shipping",
        "text": (
            "We offer free standard shipping on orders over $50. "
            "Standard shipping takes 5-7 business days. "
            "Express shipping (2-3 days) is available for $9.99."
        ),
    },
    {
        "source": "faq/account",
        "text": (
            "To reset your password, click 'Forgot Password' on the login page. "
            "You'll receive an email with a reset link valid for 24 hours. "
            "If you don't receive it, check your spam folder."
        ),
    },
    {
        "source": "faq/billing",
        "text": (
            "We accept Visa, MasterCard, American Express, and PayPal. "
            "All transactions are encrypted with TLS 1.3. "
            "For billing disputes, contact support@example.com."
        ),
    },
    {
        "source": "faq/support",
        "text": (
            "Our support team is available Monday-Friday, 9am-6pm EST. "
            "Average response time is under 2 hours. "
            "For urgent issues, use the live chat feature on our website."
        ),
    },
    {
        "source": "faq/subscription",
        "text": (
            "You can cancel your subscription at any time from your account settings. "
            "Cancellation takes effect at the end of the current billing period. "
            "No cancellation fees apply."
        ),
    },
]


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings locally using fastembed (no external API needed)."""
    print(f"Loading fastembed model '{EMBEDDING_MODEL}'...")
    model = TextEmbedding(model_name=EMBEDDING_MODEL)
    print(f"Embedding {len(texts)} documents locally...")
    return [emb.tolist() for emb in model.embed(texts)]


async def main() -> None:
    print(f"Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}...")
    client = AsyncQdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    # Recreate collection
    collections = await client.get_collections()
    if any(c.name == COLLECTION for c in collections.collections):
        await client.delete_collection(COLLECTION)
        print(f"Deleted existing collection '{COLLECTION}'")

    await client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
    )
    print(f"Created collection '{COLLECTION}' (dim={VECTOR_DIM})")

    # Embed all documents using fastembed (local, no API key needed)
    texts = [doc["text"] for doc in FAQ_DOCS]
    embeddings = get_embeddings(texts)

    # Upsert points
    points = [
        PointStruct(
            id=i,
            vector=embedding,
            payload={"text": doc["text"], "source": doc["source"]},
        )
        for i, (doc, embedding) in enumerate(zip(FAQ_DOCS, embeddings))
    ]
    await client.upsert(collection_name=COLLECTION, points=points)
    print(f"Inserted {len(points)} FAQ documents into '{COLLECTION}'")

    await client.close()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
