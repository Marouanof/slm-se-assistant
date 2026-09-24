# Training — stub S1 (QLoRA prévu S4)

Dossier vide en S1 (cf. `.gitkeep`). Le fine-tuning QLoRA arrive en
Semaine 4 sur Colab/Kaggle (GPU gratuit) :

- Base : Qwen2.5-Coder-0.5B-Instruct, 4 bits, LoRA, petits lots + accumulation.
- Dataset : sous-ensemble filtré 500–1 000 exemples, choix principal CodeAlpaca
  (MIT), fallback The-Stack-dedup (licences permissives uniquement).
- Stack principal : Unsloth ; fallback : transformers + PEFT + bitsandbytes.
- Versionning exigé : dataset + hash sha256 + licence dans `training/` et README.
- Livrable S4 : adaptateur + métadonnées, inférence locale GGUF-INT4 via
  Ollama/llama.cpp (Qwen 1.5B max si 0.5B trop faible, GGUF-INT4 CPU only).
