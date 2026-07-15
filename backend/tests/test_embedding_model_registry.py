from core.embedding_model_registry import (
    get_local_embedding_model,
    list_local_embedding_models,
)


def test_local_embedding_registry_has_supported_models():
    models = list_local_embedding_models()

    assert [model.slug for model in models] == [
        "bge-m3",
        "qwen3-embedding-0.6b",
    ]
    assert get_local_embedding_model("bge-m3").model_id == "BAAI/bge-m3"
    assert (
        get_local_embedding_model("qwen3-embedding-0.6b").model_id
        == "Qwen/Qwen3-Embedding-0.6B"
    )
