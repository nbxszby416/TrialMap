import os, re

import pandas as pd
import numpy as np

from dotenv import load_dotenv
from prompt import generate_prompt
from openai import OpenAI
from rouge_score import rouge_scorer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def llm_inference(prompt, client, model_id):
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful assistant that converts trial eligibility rules into machine-readable formats."},
                {"role": "user", "content": prompt}
            ], 
            model=model_id, 
            temperature=0.0)
        response = chat_completion.choices[0].message.content.lower()
        return response

    except Exception as e:
        return f"Error calling {model_id}: {e}"


def clean_logic_text(text: str) -> str:
    """Normalize logic expression: strip, lowercase, single-spaced."""
    return re.sub(r'\s+', ' ', text.replace('\n', ' ')).strip().lower()

def rouge_l_score(text1, text2):
    scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=False)
    predicted = clean_logic_text(text1)
    reference = clean_logic_text(text2)
    
    score = scorer.score(text1, text2)
    return round(score['rougeL'].fmeasure, 4)
    
def tfidf_similarity(str1, str2):
    vectorizer = TfidfVectorizer()
    str1 = clean_logic_text(str1)
    str2 = clean_logic_text(str2)
    tfidf_matrix = vectorizer.fit_transform([str1, str2])
    similarity = cosine_similarity(tfidf_matrix[0], tfidf_matrix[1])[0][0]
    return round(similarity,4)

def main(working_dir, trial_list):
    load_dotenv()
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    results = []
    for trial in trial_list:
        trial_path = os.path.join(working_dir, "trialEC", f"{trial}.csv")
        trial_data = pd.read_csv(trial_path).drop(columns=["Unnamed: 0"])
        criteria_name = trial_data["Criteria_Name"].to_list()
        criteria_type = trial_data["Type"].to_list()
        criteria_rule = trial_data["Enrollment"].to_list()
        ground_truth = trial_data["IE Rules in EDM"].to_list()

        rouge_l_scores = []
        tfidf_scores = []
        for name, crit_type, rule, label in zip(criteria_name, criteria_type, criteria_rule, ground_truth):
            print("################################################################")

            label = label.replace("\n\n", "\n").strip().lower()
            input_message = generate_prompt(name, crit_type, rule)
            response = llm_inference(input_message, client, model_id = "gpt-4.1").lower()[1:-1]

            rouge_l = rouge_l_score(response, label)
            tfidf = tfidf_similarity(response, label)

            rouge_l_scores.append(rouge_l)
            tfidf_scores.append(tfidf)

            results.append({
                "dataset": trial,
                "rule name": name,
                "type": crit_type,
                "original ec": rule,
                "transformed ec": response,
                "label": label,
                "rouge-l": rouge_l,
                "tf-idf": tfidf
            })

            print(f"{rule}\nROUGE-L: {rouge_l:.4f} | TF-IDF: {tfidf:.4f}\n")

        avg_rouge = np.mean(rouge_l_scores)
        std_rouge = np.std(rouge_l_scores)
        avg_tfidf = np.mean(tfidf_scores)
        std_tfidf = np.std(tfidf_scores)

        print("===================================================")
        print(f"{trial}:")
        print(f"Avg ROUGE-L: {avg_rouge:.4f} ± {std_rouge:.4f}")
        print(f"Avg TF-IDF:  {avg_tfidf:.4f} ± {std_tfidf:.4f}")
        print("===================================================")
    
    results_df = pd.DataFrame(results)
    output_path = os.path.join(working_dir, "llm_transformation_eval_results_1.csv")
    results_df.to_csv(output_path, index=False)
    print(f"Results saved to: {output_path}")

if __name__ == "__main__":
    working_dir = "/Users/bingyuz7/PycharmProjects/TrialMap/"
    trial_list = ["BI_LUX8", "BMS_Checkmate017", "BMS_Checkmate057", "BMS_Checkmate078", 
                    "Merck_Keynote010", "Merck_Keynote189", "Merck_Keynote407", "Roche_BEYOND", "Roche_OAK"]
    main(working_dir, trial_list)
