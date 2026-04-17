# BibTeX Prelude: Theoretical Foundations

This document serves as the foundation for the references in our article, specifically addressing the design choices made for the Multi-Agent System (MAS) architecture when using Small Language Models (SLMs).

## 1. The "Lost in the Middle" Phenomenon and SLM Prompting
When designing prompts for Small Language Models (like Llama-3-8B or Phi-3), we must keep them extremely concise and role-focused. If a prompt is too long or contains multiple complex instructions, SLMs suffer severely from the **"Lost in the Middle"** phenomenon, where they forget or ignore instructions placed in the middle of their context window. This degradation is much steeper in SLMs compared to massive monolithic models like GPT-4.

### Primary Reference to Cite:
To scientifically justify why our agents (Sully, Codey, Vera) have such strict, short, and specialized prompts (instead of one giant prompt doing everything), we will cite the seminal paper by **Nelson F. Liu et al. (2023/2024)**.

```bibtex
@article{liu2024lost,
  title={Lost in the middle: How language models use long contexts},
  author={Liu, Nelson F and Lin, Kevin and Hewitt, John and Paranjape, Ashwin and Bevilacqua, Michele and Petroni, Fabio and Liang, Percy},
  journal={Transactions of the Association for Computational Linguistics},
  volume={12},
  pages={157--173},
  year={2024},
  publisher={MIT Press}
}
```

**How to use it in the article text:**
> *"To mitigate context degradation and cognitive overload commonly observed in Small Language Models—a phenomenon formally known as 'Lost in the Middle' (Liu et al., 2024)—our proposed architecture decentralizes the software engineering workflow into three specialized, narrowly-prompted agents rather than relying on a single complex instruction set."*
