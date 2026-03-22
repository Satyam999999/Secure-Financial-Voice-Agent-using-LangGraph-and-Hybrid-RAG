"""
Query Expansion: rewrite user query into multiple search variants.
Fixes "not in knowledge base" when answer IS there but phrasing differs.

Example:
User asks: "Can I break my FD early?"
Expanded to:
  - "Can I break my FD early?"
  - "premature withdrawal fixed deposit"  
  - "close fixed deposit before maturity"
All three are searched — dramatically improves recall.
"""

from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
import config

EXPANSION_PROMPT = """You are a search query optimizer for a banking assistant.

Given a user's question, generate {n} alternative search queries that mean the same thing but use different words. These will be used to search a banking knowledge base.

Rules:
- Use banking terminology in some variants
- Keep each query short (under 10 words)
- Cover different ways someone might phrase the same question
- Output ONLY the queries, one per line, no numbering, no explanation

User question: {question}

Alternative queries:"""

_expander = None

def get_expander():
    global _expander
    if _expander is None:
        _expander = ChatGroq(
            model=config.MODEL_NAME,
            temperature=0.3,
            groq_api_key=config.GROQ_API_KEY,
            max_tokens=150,
        )
    return _expander

def expand_query(question: str, n: int = 3) -> list[str]:
    """
    Generate n alternative phrasings of the question.
    Returns original + expanded queries.
    Falls back to original only if expansion fails.
    """
    try:
        prompt  = ChatPromptTemplate.from_template(EXPANSION_PROMPT)
        chain   = prompt | get_expander()
        result  = chain.invoke({"question": question, "n": n})
        lines   = [l.strip() for l in result.content.strip().split("\n") if l.strip()]
        # Always include original
        all_queries = [question] + lines[:n]
        print(f"[QueryExpander] {question[:40]} → {len(all_queries)} variants")
        return all_queries
    except Exception as e:
        print(f"[QueryExpander] Failed, using original only: {e}")
        return [question]