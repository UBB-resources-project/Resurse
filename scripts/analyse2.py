import os
import sys
import base64
import torch
from dotenv import load_dotenv
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_community.llms import Ollama
from langchain_text_splitters import CharacterTextSplitter
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoModel, AutoTokenizer

class AiAnalysis:
    def __init__(self) -> None:
        # Initialize environment variables
        load_dotenv()

        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.persistent_directory = os.path.join(self.current_dir, "db", "chroma_db")

    def analyse(self, input_file_path):
        # Initialize the keyword set
        all_keywords = set()

        # Determine the file type based on the extension
        file_extension = os.path.splitext(input_file_path)[1].lower()
        
        if file_extension in [".jpg", ".jpeg", ".png", ".gif", ".bmp"]:
            with open(input_file_path, "rb") as image_file:
                image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
            
            query = f"""
            Generate a list of keywords based on the content of the following image. Use the filename to identify the subject of the image and include it in the list.

            **Requirements:**
            1. The image is related to university-level computer science.
            2. The keywords should be in English and consist of computer science or mathematics terms only.
            3. Include possible subject names like mathematics or computer science if relevant.
            4. If the image appears exam-related, include the term exam.
            5. Avoid adding terms not visible or explicitly depicted in the image. Be highly selective and avoid assumptions.
            6. The output should be a comma-separated list of likely terms, ordered by relevance.
            7. Do not add any additional text or context—just the keywords.

            **Image Content (Base64):**
            {image_base64}
            """

            ollama_base_url = os.getenv("ngrok_ollama_server")
            model_local = Ollama(base_url=ollama_base_url, model="llava:13b")

            response = model_local(query)

            # Process the text to extract keywords
            keywords = response.strip().split(", ")

            # Add the keywords to the set (to automatically handle duplicates)
            all_keywords.update(keyword.strip() for keyword in keywords)
        else:
            if file_extension == ".pdf":
                loader = PyPDFLoader(input_file_path)
            elif file_extension in [".doc", ".docx"]:
                loader = Docx2txtLoader(input_file_path)
            else:
                loader = TextLoader(input_file_path)
            
            documents = loader.load()
    
            # Split the document into chunks
            text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=10)
            docs = text_splitter.split_documents(documents)
    
            # Process each document chunk
            for i, doc in enumerate(docs):
                query = f"""
                {doc.page_content}
                get keywords from the above content. keywords shall be from cs and maths fields. 
                return only the list of keywords. 
                ... return the keywords one after another with commas on a single line
                """
    
                ollama_base_url = os.getenv("ngrok_ollama_server")
                model_local = Ollama(base_url=ollama_base_url, model="phi3:14b")
    
                response = model_local(query)
    
                # Process the text to extract keywords
                keywords = response.strip().split(", ")
    
                # Add the keywords to the set (to automatically handle duplicates)
                all_keywords.update(keyword.strip() for keyword in keywords)
    
        # Combine all unique keywords into a comma-separated string
        final_keywords = ", ".join(sorted(all_keywords, key=str.lower))

        # Load SciBERT model and tokenizer
        tokenizer = AutoTokenizer.from_pretrained("allenai/scibert_scivocab_uncased")
        model = AutoModel.from_pretrained("allenai/scibert_scivocab_uncased")

        def get_embedding(phrase):
            inputs = tokenizer(phrase, return_tensors="pt")
            outputs = model(**inputs)
            # Get the mean of the embeddings across tokens
            embedding = outputs.last_hidden_state.mean(dim=1)
            return embedding

        answer = ""
        embedding1 = get_embedding("mathematics")
        embedding2 = get_embedding("computer science")

        # Filter keywords by similarity to "mathematics" and "computer science"
        for phrase in final_keywords.split(", "):
            embedding = get_embedding(phrase)
            similarity1 = cosine_similarity(
                embedding1.detach().numpy(), embedding.detach().numpy()
            )
            similarity2 = cosine_similarity(
                embedding2.detach().numpy(), embedding.detach().numpy()
            )
            if similarity1[0][0] >= 0.6 or similarity2[0][0] >= 0.6:
                answer += phrase + ", "

        return answer.rstrip(", ")

if __name__ == "__main__":
    ai = AiAnalysis()
    keywords = ai.analyse(sys.argv[1])
    print(keywords)
