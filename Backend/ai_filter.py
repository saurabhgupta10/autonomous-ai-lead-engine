import os
from google import genai
from google.genai import types

def score_lead(leads: list[dict]) -> list[dict]:
    """
    Takes a full list of scraped leads and scores them using the official new google-genai SDK.
    """
    try:
        # नए SDK में क्लाइंट ऐसे इनिशियलाइज़ होता है (यह ऑटोमैटिकली .env से GEMINI_API_KEY उठा लेता है)
        client = genai.Client()
    except Exception as init_err:
        print(f"      [AI Error] Failed to initialize Gemini Client: {init_err}")
        # अगर क्लाइंट इनिशियलाइज़ न हो तो सबको डिफॉल्ट मीडियम देकर रिटर्न कर दो
        for lead in leads:
            lead['priority'] = "Medium"
            lead['reason'] = "Gemini initialization failed"
        return leads

    scored_leads = []
    
    for lead in leads:
        # ओरिजinal main.py के कीज़ (company_name, website, email) का इस्तेमाल
        company_name = lead.get('company_name', 'Unknown')
        website = lead.get('website', 'N/A')
        email = lead.get('email', 'N/A')
        
        try:
            prompt = f"""
            Evaluate if this company needs premium tech automation services based on their data.
            Company Name: {company_name}
            Website: {website}
            Email: {email}
            
            Return a valid JSON object with exactly two keys:
            "priority": "High" or "Medium" or "Low"
            "reason": A short 1-sentence reason why you assigned this priority.
            
            Return ONLY the raw JSON block. No markdown, no code fences.
            """
            
            response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt
            )
            
            # जेमिनी के रिस्पॉन्स से टेक्स्ट निकाल कर क्लीन करना
            clean_text = response.text.strip().replace("```json", "").replace("```", "").strip()
            
            # रिस्पॉन्स को पार्स करना
            import json
            data = json.loads(clean_text)
            
            lead['priority'] = data.get('priority', 'Medium')
            lead['reason'] = data.get('reason', 'Analyzed by AI engine.')
            
        except Exception as e:
            # बैकअप स्कोरर अगर किसी सिंगल कॉल में कोई दिक्कत आए
            lead['priority'] = "Medium"
            lead['reason'] = f"Gemini scoring failed: {str(e)}"
            
        scored_leads.append(lead)
        
    return scored_leads
