// Demo 模式 — 无需后端的完整产品预览
import type { PaperItem } from '../types/paper'
import type { SourceCard } from '../types/source'
import type { ContentBlock } from '../types/content'
import type { AssistantMessage, ConversationRecord } from '../types/message'

// ─── 检测 demo 模式 ───
export function isDemoMode(): boolean {
  return typeof window !== 'undefined' && new URLSearchParams(window.location.search).has('demo')
}

// ─── Mock 论文数据 ───
export const DEMO_PAPERS: PaperItem[] = [
  {
    paper_id: 'paper-1',
    title: 'Attention Is All You Need',
    authors: 'Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones',
    year: '2017',
    keywords: ['attention', 'transformer', 'self-attention', 'encoder-decoder', 'neural machine translation'],
    file_path: '/data/papers/attention-is-all-you-need.pdf',
    file_hash: 'a1b2c3',
    chunk_count: 47,
    total_pages: 11,
    import_time: '2026-05-20T10:30:00Z',
    status: 'completed',
    library_item_id: 'paper-1',
    kind: 'pdf',
    file_size: 1250000,
  },
  {
    paper_id: 'paper-2',
    title: 'BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding',
    authors: 'Jacob Devlin, Ming-Wei Chang, Kenton Lee, Kristina Toutanova',
    year: '2019',
    keywords: ['bert', 'pre-training', 'language model', 'masked language model', 'nlu'],
    file_path: '/data/papers/bert.pdf',
    file_hash: 'd4e5f6',
    chunk_count: 62,
    total_pages: 16,
    import_time: '2026-05-21T14:20:00Z',
    status: 'completed',
    library_item_id: 'paper-2',
    kind: 'pdf',
    file_size: 2100000,
  },
  {
    paper_id: 'paper-3',
    title: 'Deep Residual Learning for Image Recognition',
    authors: 'Kaiming He, Xiangyu Zhang, Shaoqing Ren, Jian Sun',
    year: '2016',
    keywords: ['resnet', 'residual learning', 'skip connection', 'image classification', 'deep network'],
    file_path: '/data/papers/resnet.pdf',
    file_hash: 'g7h8i9',
    chunk_count: 38,
    total_pages: 12,
    import_time: '2026-05-22T09:15:00Z',
    status: 'completed',
    library_item_id: 'paper-3',
    kind: 'pdf',
    file_size: 3800000,
  },
  {
    paper_id: 'paper-4',
    title: 'Generative Adversarial Networks',
    authors: 'Ian Goodfellow, Jean Pouget-Abadie, Mehdi Mirza, Bing Xu',
    year: '2014',
    keywords: ['gan', 'generative model', 'adversarial training', 'discriminator', 'generator'],
    file_path: '/data/papers/gan.pdf',
    file_hash: 'j0k1l2',
    chunk_count: 28,
    total_pages: 9,
    import_time: '2026-05-23T16:45:00Z',
    status: 'completed',
    library_item_id: 'paper-4',
    kind: 'pdf',
    file_size: 890000,
  },
  {
    paper_id: 'paper-5',
    title: 'GPT-4 Technical Report',
    authors: 'OpenAI, Josh Achiam, Steven Adler, Sandhini Agarwal',
    year: '2023',
    keywords: ['gpt-4', 'large language model', 'multimodal', 'rlhf', 'scaling'],
    file_path: '/data/papers/gpt4-report.pdf',
    file_hash: 'm3n4o5',
    chunk_count: 85,
    total_pages: 100,
    import_time: '2026-05-25T11:00:00Z',
    status: 'completed',
    library_item_id: 'paper-5',
    kind: 'pdf',
    file_size: 15000000,
  },
]

// ─── Mock 对话历史 ───
export interface DemoSession {
  session_id: string
  title: string
  created_at: string
  messages: ConversationRecord[]
}

export const DEMO_SESSIONS: DemoSession[] = [
  {
    session_id: 'session-1',
    title: 'Transformer 架构分析',
    created_at: '2026-05-26T10:00:00Z',
    messages: [
      {
        id: 'user-1',
        role: 'user',
        content: '帮我分析 Attention Is All You Need 这篇论文的核心贡献',
        createdAt: '2026-05-26T10:01:00Z',
      },
      {
        id: 'assistant-1',
        role: 'assistant',
        createdAt: '2026-05-26T10:01:02Z',
        thinking: '用户要求分析 Transformer 论文的核心贡献。我需要从注意力机制、架构设计、实验结果几个维度来组织回答。首先回顾论文背景——当时 NLP 任务主要依赖 RNN/CNN 序列模型，Transformer 提出了全新的纯注意力架构。',
        thinkingTimeMs: 3200,
        blocks: [
          { type: 'heading', text: '核心贡献', level: 2 },
          { type: 'paragraph', text: '《Attention Is All You Need》由 Vaswani 等人在 2017 年提出，彻底改变了自然语言处理领域的技术路线。其核心贡献可以概括为以下三点：' },
          { type: 'heading', text: '1. 多头自注意力机制（Multi-Head Self-Attention）', level: 3 },
          { type: 'paragraph', text: '论文提出了多头注意力机制，将 Query、Key、Value 分别通过 h 个不同的线性投影，并行计算注意力。这使得模型能够同时关注不同位置的不同表示子空间的信息。公式为：' },
          { type: 'code', text: 'MultiHead(Q, K, V) = Concat(head_1, ..., head_h)W^O\nwhere head_i = Attention(QW_i^Q, KW_i^K, VW_i^V)', language: 'python' },
          { type: 'heading', text: '2. 位置编码（Positional Encoding）', level: 3 },
          { type: 'paragraph', text: '由于 Transformer 不包含递归和卷积结构，模型本身没有序列位置感知能力。论文使用正弦和余弦函数生成位置编码，注入到输入嵌入中，使模型能够利用序列的顺序信息。' },
          { type: 'heading', text: '3. 编码器-解码器架构', level: 3 },
          { type: 'paragraph', text: '完整的 Transformer 由 N=6 个编码器层和 N=6 个解码器层堆叠而成。每个编码器层包含一个多头自注意力子层和一个前馈网络子层。解码器额外增加了编码器-解码器注意力层。' },
          { type: 'heading', text: '实验结果', level: 2 },
          { type: 'paragraph', text: '在 WMT 2014 英德翻译任务上，Transformer (big) 模型以 28.4 BLEU 超过了当时所有已有模型（包括集成模型），提升了 2.0 BLEU。在英法翻译任务上，达到了 41.8 BLEU 的 SOTA 结果。' },
        ],
        sources: [
          { id: 'src-1', paper_id: 'paper-1', title: 'Attention Is All You Need', page: 3, section: '3 Model Architecture', content: 'The encoder is composed of a stack of N = 6 identical layers...' },
          { id: 'src-2', paper_id: 'paper-2', title: 'BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding', page: 4, section: '3.1 Pre-training Tasks', content: 'We introduce a new pre-training objective, Masked Language Modeling (MLM), which masks random tokens and trains the model to predict them using bidirectional context...' },
          { id: 'src-3', paper_id: 'paper-1', title: 'Attention Is All You Need', page: 8, section: '5.3 Results', content: 'On the WMT 2014 English-to-German translation task, the big transformer model outperforms the best models...' },
        ],
      } as AssistantMessage,
    ],
  },
  {
    session_id: 'session-2',
    title: 'BERT 与 GPT 对比',
    created_at: '2026-05-27T15:30:00Z',
    messages: [
      {
        id: 'user-2',
        role: 'user',
        content: 'BERT 和 GPT 的预训练策略有什么区别？',
        createdAt: '2026-05-27T15:31:00Z',
      },
      {
        id: 'assistant-2',
        role: 'assistant',
        createdAt: '2026-05-27T15:31:01Z',
        thinking: '',
        thinkingTimeMs: 0,
        blocks: [
          { type: 'paragraph', text: 'BERT 和 GPT 是两种最具影响力的预训练语言模型，它们的预训练策略存在本质区别：' },
          { type: 'heading', text: '架构差异', level: 3 },
          { type: 'paragraph', text: 'BERT 使用 **双向 Transformer 编码器**，能够同时看到上下文信息；GPT 使用 **单向 Transformer 解码器**，只能看到当前位置之前的 token。' },
          { type: 'heading', text: '预训练目标', level: 3 },
          { type: 'list', items: [
            'BERT：掩码语言模型（MLM）+ 下一句预测（NSP）。随机遮盖 15% 的 token，要求模型预测被遮盖的词。',
            'GPT：自回归语言模型。给定前文，预测下一个 token 的概率分布。',
          ] },
          { type: 'heading', text: '适用场景', level: 3 },
          { type: 'paragraph', text: 'BERT 更擅长理解型任务（分类、匹配、抽取），GPT 更擅长生成型任务（文本续写、对话、代码生成）。两者在 NLU 和 NLG 上的表现各有侧重。' },
        ],
        sources: [
          { id: 'src-4', paper_id: 'paper-2', title: 'BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding', page: 2, section: '3.1 Masked LM', content: 'We mask 15% of the WordPiece tokens at random...' },
          { id: 'src-5', paper_id: 'paper-4', title: 'Generative Adversarial Networks', page: 2, section: '3 Adversarial Training', content: 'The generative model G captures the data distribution by minimizing the log probability of the discriminator being correct...' },
          { id: 'src-6', paper_id: 'paper-4', title: 'Generative Adversarial Networks', page: 5, section: '4.1 Global Optimum', content: 'The generator recovers the data distribution as training converges to the global optimum of the minimax game...' },
        ],
      } as AssistantMessage,
    ],
  },
]

// ─── Mock AI 回复模板 ───
interface MockResponse {
  thinking?: string
  thinkingTimeMs?: number
  blocks: ContentBlock[]
  sources: SourceCard[]
}

function pickSources(paperIds: string[]): SourceCard[] {
  // Ensure at least 2 different papers appear in sources for multi-citation display
  const uniqueIds = [...new Set(paperIds)]
  if (uniqueIds.length < 2) {
    // Add a second paper from the demo library that isn't already present
    const fallback = DEMO_PAPERS.find(p => !uniqueIds.includes(p.paper_id))
    if (fallback) uniqueIds.push(fallback.paper_id)
  }
  // Use up to 3 sources, distributing across papers
  const ids = uniqueIds.slice(0, 3).length >= 2 ? uniqueIds.slice(0, 3) : [...uniqueIds.slice(0, 3), ...DEMO_PAPERS.filter(p => !uniqueIds.includes(p.paper_id)).map(p => p.paper_id).slice(0, 2 - uniqueIds.length)]
  const sources: SourceCard[] = []
  for (let i = 0; i < Math.min(ids.length, 3); i++) {
    const pid = ids[i]
    const paper = DEMO_PAPERS.find(p => p.paper_id === pid)
    if (paper) {
      const page = Math.floor(Math.random() * paper.total_pages) + 1
      const snippets: Record<string, string> = {
        'paper-1': 'The multi-head attention mechanism allows the model to jointly attend to information from different representation subspaces at different positions.',
        'paper-2': 'By jointly conditioning on both left and right context in all layers, the pre-trained BERT model can be fine-tuned with just one additional output layer.',
        'paper-3': 'Deep residual learning provides a way to train substantially deeper networks by learning residual functions with reference to the layer inputs.',
        'paper-4': 'The generative model learns a mapping from random noise to the data distribution through an adversarial training process with the discriminator.',
        'paper-5': 'GPT-4 demonstrates significant capability improvements across a wide range of professional and academic benchmarks.',
      }
      sources.push({
        id: `src-${pid}-${Date.now()}-${i}`,
        paper_id: pid,
        title: paper.title,
        page,
        section: i === 0 ? 'Introduction' : 'Results',
        content: snippets[pid as string] ?? `这是从《${paper.title}》中检索到的相关段落，展示了该研究的核心发现和方法论贡献。`,
      })
    }
  }
  return sources
}

const RESPONSE_TEMPLATES: Record<string, (prompt: string, paperIds: string[]) => MockResponse> = {
  default: (prompt, paperIds) => ({
    thinking: `用户的问题涉及"${prompt.slice(0, 30)}..."。让我从已有的文献库中检索相关信息，整合多篇论文的观点来回答。`,
    thinkingTimeMs: 1800 + Math.random() * 1500,
    blocks: [
      { type: 'heading', text: '分析结果', level: 2 },
      { type: 'paragraph', text: `基于您的问题"${prompt.slice(0, 50)}"，我对相关文献进行了深度检索和分析。以下是综合结论：` },
      { type: 'heading', text: '关键发现', level: 3 },
      { type: 'paragraph', text: '从检索到的文献中，可以归纳出以下几个核心观点。首先，Transformer 架构通过自注意力机制实现了对长距离依赖的有效建模，这为后续的 BERT、GPT 等模型奠定了基础。其次，预训练+微调的范式在大规模语料上展现出了显著的迁移学习优势。' },
      { type: 'heading', text: '方法论启示', level: 3 },
      { type: 'list', items: [
        '多任务学习框架可以有效提升模型的泛化能力',
        '数据规模和模型规模的协同扩展是提升性能的关键',
        '注意力机制的可解释性为理解模型决策提供了窗口',
      ] },
      { type: 'heading', text: '建议方向', level: 3 },
      { type: 'paragraph', text: '建议进一步探索高效注意力机制的变体（如 Linformer、Flash Attention），以及如何将领域知识融入预训练过程中以获得更好的下游任务表现。' },
    ],
    sources: pickSources(paperIds),
  }),

  analysis: (_prompt, paperIds) => ({
    thinking: `用户要求进行论文分析。我需要从研究背景、方法论、实验设计和贡献四个维度来组织回答。先检索相关论文的关键段落。`,
    thinkingTimeMs: 2500 + Math.random() * 1000,
    blocks: [
      { type: 'heading', text: '论文深度分析', level: 2 },
      { type: 'paragraph', text: `以下是对您查询的详细分析：` },
      { type: 'heading', text: '研究背景', level: 3 },
      { type: 'paragraph', text: '该研究处于深度学习与自然语言处理交叉领域的前沿。传统方法在处理长序列和复杂语义关系时存在局限性，这促使研究者探索新的架构设计。' },
      { type: 'heading', text: '核心方法', level: 3 },
      { type: 'paragraph', text: '论文提出的方法基于注意力机制，通过并行计算大幅提升了训练效率。关键创新在于多头注意力设计，允许模型同时关注不同位置和不同表示子空间的信息。' },
      { type: 'code', text: '# 注意力计算伪代码\nQ = X @ W_q  # [batch, seq_len, d_k]\nK = X @ W_k  # [batch, seq_len, d_k]\nV = X @ W_v  # [batch, seq_len, d_v]\nattention = softmax(Q @ K.T / sqrt(d_k)) @ V', language: 'python' },
      { type: 'heading', text: '实验结论', level: 3 },
      { type: 'paragraph', text: '实验结果表明，该方法在多项基准测试上取得了显著提升。特别是在需要捕捉长距离依赖的任务上，性能提升尤为明显，BLEU 分数提高了约 2 个点。' },
    ],
    sources: pickSources(paperIds),
  }),
}

function matchTemplate(prompt: string): (prompt: string, paperIds: string[]) => MockResponse {
  if (/分析|解读|贡献|方法|实验/.test(prompt)) return RESPONSE_TEMPLATES.analysis
  return RESPONSE_TEMPLATES.default
}

// ─── 模拟流式输出 ───
export function mockSendPrompt(
  prompt: string,
  paperIds: string[],
  handlers: {
    onThinking: (text: string, timeMs: number) => void
    onBlock: (block: ContentBlock) => void
    onSources: (sources: SourceCard[]) => void
    onDone: () => void
    onStatus?: (phase: string, message: string) => void
  },
): { cancel: () => void } {
  let cancelled = false
  const template = matchTemplate(prompt)
  const response = template(prompt, paperIds)
  const timers: ReturnType<typeof setTimeout>[] = []

  function schedule(fn: () => void, delay: number) {
    if (cancelled) return
    const t = setTimeout(() => {
      if (!cancelled) fn()
    }, delay)
    timers.push(t)
  }

  // Phase 0: Status events
  schedule(() => handlers.onStatus?.('retrieving', '正在查询文献库...'), 200)
  schedule(() => handlers.onStatus?.('generating', '正在生成回答...'), 1800)

  // Phase 1: Thinking
  if (response.thinking) {
    const thinkingText = response.thinking
    const chunkSize = 8
    for (let i = 0; i < thinkingText.length; i += chunkSize) {
      const chunk = thinkingText.slice(i, i + chunkSize)
      schedule(() => handlers.onThinking(chunk, response.thinkingTimeMs || 0), 60 * (i / chunkSize))
    }
  }

  // Phase 2: Blocks
  const blockStart = response.thinking ? response.thinkingTimeMs! + 500 : 500
  let blockDelay = blockStart
  for (const block of response.blocks) {
    schedule(() => handlers.onBlock(block), blockDelay)
    blockDelay += 120 + Math.random() * 80
  }

  // Phase 3: Sources
  if (response.sources.length > 0) {
    schedule(() => handlers.onSources(response.sources), blockDelay + 200)
  }

  // Phase 4: Done
  schedule(() => handlers.onDone(), blockDelay + 600)

  return {
    cancel() {
      cancelled = true
      timers.forEach(clearTimeout)
    },
  }
}
