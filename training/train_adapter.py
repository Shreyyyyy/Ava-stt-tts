"""
LoRA / QLoRA fine-tuning pipeline for AVA.

Usage (manual):
    python training/train_adapter.py

Or triggered via the API endpoint POST /training/trigger.

Requirements (install separately to keep base env light):
    pip install -r requirements-training.txt
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

ADAPTERS_DIR = Path(__file__).parent.parent / "adapters"
DATASETS_DIR = Path(__file__).parent.parent / "training" / "datasets"
LOG_FILE     = Path(__file__).parent.parent / "logs" / "training.log"


def _setup_file_logger():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(str(LOG_FILE))
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)


def _build_dataset(min_score: float, max_examples: int) -> list:
    """Pull high-quality examples from the database and format for fine-tuning."""
    from memory.database import get_high_quality_examples, mark_as_trained

    examples = get_high_quality_examples(min_score=min_score, limit=max_examples)
    if not examples:
        logger.warning("No training examples found meeting the quality threshold.")
        return []

    formatted = []
    for ex in examples:
        # If the user provided a correction, use that as the expected output
        output = ex.get("user_correction") or ex.get("model_response", "")
        if not output:
            continue
        formatted.append({
            "instruction": ex["user_message"],
            "output":      output,
            "score":       ex.get("feedback_score", 0.5),
            "id":          ex["id"],
        })

    logger.info(f"Dataset built: {len(formatted)} examples (min_score={min_score})")
    return formatted


def _save_dataset(data: list, version: str) -> Path:
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    path = DATASETS_DIR / f"dataset_{version}.jsonl"
    with open(path, "w") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")
    logger.info(f"Dataset saved → {path}")
    return path


def _run_lora_training(
    dataset_path: Path,
    base_model: str,
    adapter_out_dir: Path,
    training_config: dict,
):
    """
    Run QLoRA fine-tuning via HuggingFace PEFT + TRL.
    Adjust config values to match your GPU VRAM.
    """
    import torch
    from datasets import Dataset
    from transformers import (
        AutoTokenizer,
        AutoModelForCausalLM,
        BitsAndBytesConfig,
        TrainingArguments,
    )
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from trl import SFTTrainer

    # ── Load dataset ─────────────────────────────────────────────────────────
    data = []
    with open(dataset_path) as f:
        for line in f:
            data.append(json.loads(line))

    def format_example(ex):
        return {
            "text": (
                f"### Instruction:\n{ex['instruction']}\n\n"
                f"### Response:\n{ex['output']}"
            )
        }

    hf_dataset = Dataset.from_list([format_example(d) for d in data])

    # ── Quantisation config ───────────────────────────────────────────────────
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

    # ── Model + tokenizer ────────────────────────────────────────────────────
    # NOTE: For Ollama use-case, we train with HF weights and then
    # export the adapter. Point model_name to your HF model path/id.
    model_name = training_config.get("hf_model_name", "meta-llama/Meta-Llama-3-8B")
    logger.info(f"Loading base model: {model_name}")

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    # ── LoRA config ───────────────────────────────────────────────────────────
    lora_cfg = LoraConfig(
        r=training_config.get("lora_r", 16),
        lora_alpha=training_config.get("lora_alpha", 32),
        target_modules=training_config.get("target_modules", ["q_proj", "v_proj"]),
        lora_dropout=training_config.get("lora_dropout", 0.05),
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    # ── Training arguments ────────────────────────────────────────────────────
    train_args = TrainingArguments(
        output_dir=str(adapter_out_dir),
        num_train_epochs=training_config.get("epochs", 3),
        per_device_train_batch_size=training_config.get("batch_size", 2),
        gradient_accumulation_steps=training_config.get("grad_accum", 4),
        learning_rate=training_config.get("lr", 2e-4),
        fp16=False,
        bf16=True,
        logging_steps=10,
        save_strategy="epoch",
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        report_to="none",
    )

    # ── Train ─────────────────────────────────────────────────────────────────
    trainer = SFTTrainer(
        model=model,
        train_dataset=hf_dataset,
        args=train_args,
        dataset_text_field="text",
        max_seq_length=training_config.get("max_seq_length", 2048),
    )
    trainer.train()
    trainer.model.save_pretrained(str(adapter_out_dir))
    tokenizer.save_pretrained(str(adapter_out_dir))
    logger.info(f"Adapter saved → {adapter_out_dir}")


def run_training_pipeline(
    base_model: str = "llama3.2",
    min_score: float = 0.7,
    max_examples: int = 500,
    notes: str = "",
    training_config: Optional[dict] = None,
):
    """
    End-to-end training pipeline:
      1. Pull high-quality examples from the database
      2. Save a versioned JSONL dataset
      3. Fine-tune a LoRA adapter
      4. Save the adapter to /adapters/<version>/
      5. Log the run to the database
    """
    _setup_file_logger()

    from memory.database import log_training_run, update_training_run, mark_as_trained

    version = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    config  = training_config or {}

    run_id = log_training_run(
        adapter_version=version,
        dataset_size=0,
        base_model=base_model,
        config=config,
    )

    try:
        # 1. Build dataset
        data = _build_dataset(min_score=min_score, max_examples=max_examples)
        if not data:
            update_training_run(run_id, "skipped", "No qualifying examples found.")
            return

        # 2. Save dataset
        dataset_path = _save_dataset(data, version)

        # 3. Prepare output dir
        adapter_out = ADAPTERS_DIR / version
        adapter_out.mkdir(parents=True, exist_ok=True)

        # 4. Fine-tune
        _run_lora_training(
            dataset_path=dataset_path,
            base_model=base_model,
            adapter_out_dir=adapter_out,
            training_config=config,
        )

        # 5. Write version manifest
        manifest = {
            "version":   version,
            "base_model": base_model,
            "dataset":   str(dataset_path),
            "examples":  len(data),
            "config":    config,
            "created_at": datetime.utcnow().isoformat(),
            "notes":     notes,
        }
        with open(adapter_out / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)

        # 6. Update database
        trained_ids = [d["id"] for d in data]
        mark_as_trained(trained_ids)
        update_training_run(run_id, "completed", notes)

        # 7. Symlink "latest"
        latest_link = ADAPTERS_DIR / "latest"
        if latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(adapter_out)
        logger.info(f"Training complete. Adapter version: {version}")

    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        update_training_run(run_id, "failed", str(e))
        raise


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry-point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AVA LoRA Training Pipeline")
    parser.add_argument("--model",        default="llama3.2",         help="Ollama / HF model name")
    parser.add_argument("--min-score",    default=0.7,  type=float, help="Minimum feedback score for training examples")
    parser.add_argument("--max-examples", default=500,  type=int,   help="Maximum number of training examples")
    parser.add_argument("--epochs",       default=3,    type=int,   help="Training epochs")
    parser.add_argument("--batch-size",   default=2,    type=int,   help="Per-device batch size")
    parser.add_argument("--lora-r",       default=16,   type=int,   help="LoRA rank")
    parser.add_argument("--notes",        default="",               help="Notes for this training run")
    parser.add_argument(
        "--hf-model-name",
        default="meta-llama/Meta-Llama-3-8B",
        help="HuggingFace model name or local path for the base model weights",
    )
    args = parser.parse_args()

    config = {
        "hf_model_name": args.hf_model_name,
        "epochs":        args.epochs,
        "batch_size":    args.batch_size,
        "lora_r":        args.lora_r,
        "lora_alpha":    args.lora_r * 2,
    }

    run_training_pipeline(
        base_model=args.model,
        min_score=args.min_score,
        max_examples=args.max_examples,
        notes=args.notes,
        training_config=config,
    )
