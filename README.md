# ollama server miniforge window

conda activate llm
set OLLAMA_NUM_GPU=999
set ZES_ENABLE_SYSMAN=1
set SYCL_CACHE_PERSISTENT=1
set no_proxy=localhost,127.0.0.1
set OLLAMA_HOST=0.0.0.0
ollama serve

# other miniforge window for llm if needed
conda activate llm
ollama run qwen3:8b

# pull a new model
ollama pull qwen3:8b