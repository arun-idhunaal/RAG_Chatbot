# **INDmoney Mutual Fund FAQ Chatbot – Product Brief**

**Background:** India’s mutual fund industry has grown rapidly, offering investors a vast number of schemes (over 1,400 schemes as of mid-2023). Retail investors seeking to compare funds often struggle to find key factual details (expense ratios, lock-in periods, SIP amounts, etc.) because this information is scattered across various sources – official scheme documents, AMC websites, regulatory filings, and broker portals. As one industry report notes, answers to basic mutual fund questions are often “buried in PDFs, AMC portals, and SEBI documents”. This fragmentation makes it time-consuming for users (and support staff) to manually extract and compare facts for decision-making.

**Problem:** Retail users and brokerage support teams face repetitive, factual queries about mutual funds (e.g. “What is the expense ratio of Fund X?”, “What is the lock-in period for this ELSS?”). Obtaining these answers requires navigating multiple sites and documents. For example, ELSS funds have a mandatory 3-year lock-in, but this fact may be hidden in scheme prospectuses. Without a streamlined source of truth, users either rely on customer support (increasing costs) or spend significant time searching.

**Opportunity:** A specialized FAQ chatbot can address this pain point by providing **instant, accurate, and cited answers** to common mutual-fund queries. By leveraging a retrieval-augmented pipeline over official sources, the chatbot would “turn scattered AMC documents into a single, trustworthy, facts-only conversational assistant”. The goal is to empower investors with factual information at their fingertips while reducing repetitive support workloads.

## Objectives & Scope

- **Factual Q\&A Only:** The bot will answer *only objective, factual questions* about mutual fund schemes (e.g. NAV, expense ratio, exit load, minimum SIP, lock-in, riskometer, benchmark, statement download procedures). It will cite *official sources* (AMC factsheets, scheme offer documents, SEBI/AMFI materials) for every answer. No opinions or personalized advice will be given under any circumstances.  
    
- **Supported Schemes:** Initially focus on the mutual fund schemes listed in the provided SOURCE\_LIST\_RAGMFCHATBOT.md (INDmoney’s curated list of AMC scheme URLs). For a query about a scheme not in this list, the chatbot should politely say it doesn’t have data for that scheme and list the supported scheme names.  
    
- **General Factual Queries:** The bot can also answer general mutual-fund questions (e.g. “What is an exit load?”, “How to download a capital gains statement?”) by searching *non-scheme-specific sources* from the source list. All answers must come from verifiable, authoritative sources.  
    
- **Advice and Opinion:** Any question asking for advice, recommendation, or opinion (e.g. “Which fund is best?”, “Should I invest in equity now?”) is out of scope. The chatbot must respond to these with a polite refusal (e.g. “I’m sorry, I only provide factual information”) and direct users to educational material or disclaimers. If a query mixes factual and advisory parts, the bot should answer only the factual part and gently refuse the rest with a “facts-only” message.  
    
- **User Types:** The primary users are retail INDmoney app users researching funds and INDmoney support staff handling mutual fund queries. The chatbot is designed to enhance their experience by providing quick, reliable information and to free support agents for complex issues.  
    
- **Channels:** The chatbot (“**INDmoney MF Support**”) will be embedded in the INDmoney platform (in-app/web) with a simple chat UI. It will greet users with a welcome message, show three example questions to guide them, and display a disclaimer snippet ("Facts-only. No investment advice").

## Chatbot Behavior and Flow

1. **Query Classification:** On receiving input, the chatbot first classifies the intent:  
     
   - *Scheme-specific factual:* Queries explicitly about a particular fund scheme (e.g. “What is the expense ratio of \[Scheme Name\]?”).  
   - *General factual:* Objective questions not tied to a specific scheme (e.g. “What is an exit load?”, “How do I download my statement?”).  
   - *Advisory:* Any request for investment advice, recommendations, opinions, or subjective comparisons.  
   - *Mixed:* Contains both factual and advisory elements.

   

2. **Scheme Factual Query Handling:** If the query is scheme-specific:  
     
   - **Source Selection:** Look up the scheme in the provided sources list. If found, use only that scheme’s official documents (AMC factsheet, KIM/SID, AMC portal page) to retrieve the answer. Do not search third-party sites or blogs.  
   - **Unknown Scheme:** If the scheme is not in our source list, reply politely that the scheme is unknown. Provide a list of the supported schemes (e.g. “I have information only for these schemes: …”).  
   - **Answering:** Use the RAG pipeline to retrieve relevant facts and generate an answer. Provide a concise factual answer (1–3 sentences) and include at least one clear citation of the exact source in the response. For example:  
     - *Q:* “What is the lock-in period for XYZ ELSS fund?”  
       *A:* “ELSS funds have a mandatory lock-in period of 3 years from the investment date.”  
     - *Q:* “What is the expense ratio of \[Fund Y\]?”  
       (Answer with value and source.)

   

3. **General Factual Query Handling:** If the query is factual but not about a specific scheme:  
     
   - Consult only the designated general knowledge sources (as per SOURCE\_LIST, e.g. industry FAQs, regulatory guides). Provide a factual answer with citation(s).  
   - Example: *Q:* “How do I get my capital gains statement?” *A:* “Capital gains statements can be generated from the AMC’s portal or broker app by selecting the financial year.”

   

4. **Advisory Query Handling:** If the query requests advice or opinion:  
     
   - The chatbot will *refuse* with a polite, facts-only message (e.g. “I’m sorry, I cannot provide investment advice. I can only share factual information about mutual funds.”). Optionally include a link to an educational or regulatory page (e.g. SEBI investor education) as a resource.

   

5. **Mixed Queries:** If the question has both factual and advisory parts:  
     
   - Extract and answer only the factual portion, following the rules above. At the end of the answer, append the standard refusal (e.g. “I’m designed to give only factual answers, not opinions. Thank you for understanding.”).

   

6. **Answer Style Guidelines:**  
     
   - *Conciseness:* Keep answers brief (preferably no more than 2–3 sentences) to maintain clarity.  
   - *Clarity:* Use straightforward, user-friendly language. Avoid jargon or vague phrasing.  
   - *Citations:* Every answer must include at least one inline citation to the exact source (e.g. Factsheet page, AMC FAQ) from the RAG retrieval. This builds trust and allows verification. For example: “…3 years”.  
   - *No Extraneous Data:* Do not compute or compare fund returns; if a user requests comparative performance, respond with a citation to the official factsheet and suggest the user check the factsheet for full details.

   

7. **UI Elements:**  
     
   - The chat interface will be a clean, mobile-friendly widget (dark or light theme consistent with INDmoney’s design). As in similar fintech chatbots, it will display example question buttons and a prominent compliance disclaimer.  
   - Upon opening, the chatbot shows a welcome message (e.g. “Hello\! I’m INDmoney MF Support. Ask me about any fund’s facts.”) along with 3 clickable example questions to help users start. The welcome text clearly states the “facts-only” policy.  
   - All responses show the cited source link (and page if possible). For compliance, a short disclaimer is always visible (e.g. “🔒 I provide factual info only; not personal financial advice.”).

## Example Interaction Flows

- Listed on SAMPLE\_Q\&A\_RAGMFCHATBOT.md file for all types of queries mentioned in this document.

## Data and Technology

- **Retrieval-Augmented Generation (RAG) Engine:** We will implement a RAG-based pipeline to ensure accuracy. This means the chatbot combines a vector store (holding the ingested documents) with a language model that generates answers grounded in retrieved content. RAG ensures the LLM references authoritative sources and stays up-to-date.  
    
- **Knowledge Base:**  
    
  - *Scheme Documents:* The SOURCE\_LIST\_RAGMFCHATBOT.md provides URLs of official AMC pages (fact sheets, KIMs, SID) for each supported scheme. We will scrape and ingest these documents (textual content, tables, etc.) into the system.  
  - *General MF Sources:* A curated set of non-scheme resources (e.g. AMFI website FAQs, SEBI circulars, INDmoney help pages) to answer general questions.


- **Data Pipeline:**  
    
  - Use a web scraping to fetch the latest scheme documents/general facts from public SEBI/AMC/AMFI pages. Embeddings, Data ingestion frequecny, cleaning, chunking and database, LLM call and techstack all will be detailed in the architecture.md file.


- **Compliance & Security:**  
    
  - All answers come from pre-checked, public-domain knowledge; no personal data is stored or processed. The bot will actively **reject any attempt** to provide personal identifiers (PAN, Aadhaar, OTP, phone).  
  - We will ensure data privacy and secure hosting (e.g. SOC-2 standards) since financial information is sensitive.

## Benefits and Metrics

A well-executed FAQ chatbot will deliver measurable impact:

- **For users:** Immediate access to accurate fund facts (no need to search PDFs or call support). This should raise user satisfaction and trust. As one prototype noted, investors get “instant access to factual information” without digging through documents.  
- **For support teams:** The bot can handle up to 80–90% of repetitive queries, freeing agents for complex issues. This reduces workload and costs. The HDFC Mutual Fund bot report highlights “reduced repetitive query handling” and “freed up time for complex issues” as key gains.  
- **For INDmoney:** Consistent answers increase brand trust; fewer phone/email queries lowers support overhead. Long-term, we can track metrics like number of queries answered, deflection rate, and user feedback ratings.

We will define success by increased user engagement with the bot and a drop in mutual-fund-related support tickets over time.

## Next Steps

1. **Data Preparation:** Gather and parse all sources from SOURCE\_LIST\_RAGMFCHATBOT.md. Clean and store them in the vector DB.  
2. **Prototype RAG Pipeline:** Develop the retrieval chain and test sample queries, tuning the LLM prompts for concise answers and correct citations.  
3. **UI Integration:** Design the chat interface with sample prompts and disclaimer. Iterate on tone (friendly yet factual) based on user testing.  
4. **Testing & QA:** Validate the bot with a wide range of factual questions, as well as edge cases (unknown schemes, mixed queries). Ensure refusal rules work.  
5. **Launch & Monitor:** Deploy the bot to a test user group (or a subset of the app). Monitor usage, collect feedback, and refine data sources/answers.

With this focused approach (grounded in official data and strict compliance), the INDmoney MF Support chatbot will make mutual fund research easy and reliable for users while adhering to regulatory and company guidelines.