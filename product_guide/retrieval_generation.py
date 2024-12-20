import numpy as np
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import MessagesPlaceholder
from langchain.chains import create_history_aware_retriever
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from flipkart.data_ingestion import data_ingestion

from dotenv import load_dotenv
import os

def find_top_matching(data, selected_values, top_n=5):
    """
    Find the top matching items based on the selected values.
    """
    return data.head(top_n)

def get_recommendations(model, scaler, input_vector, storage, size):
    """
    Predict price and return the unscaled prediction.
    """
    scaled_prediction = model.predict(input_vector)
    full_array = np.array([[scaled_prediction[0], scaler.transform([[0, storage, 0]])[0][1], size]])
    predicted_price = scaler.inverse_transform(full_array)[0][0]
    return predicted_price


load_dotenv()

os.environ["GROQ_API_KEY"]= os.getenv("GROQ_API_KEY")

model = ChatGroq(model="llama-3.1-70b-versatile", temperature=0.5)


chat_history= []
store = {}
def get_session_history(session_id: str)-> BaseChatMessageHistory:
  if session_id not in store:
    store[session_id]= ChatMessageHistory()
  return store[session_id]


def generation(vstore):
    retriever = vstore.as_retriever(search_kwargs={"k": 3})

    retriever_prompt = ("Given a chat history and the latest user question which might reference context in the chat history,"
    "formulate a standalone question which can be understood without the chat history."
    "Do NOT answer the question, just reformulate it if needed and otherwise return it as is."
    )

    contextualize_q_prompt = ChatPromptTemplate.from_messages(
    [
    ("system", retriever_prompt),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    ]
)
    history_aware_retriever = create_history_aware_retriever(model, retriever, contextualize_q_prompt)
    PRODUCT_BOT_TEMPLATE = """
    You are a specialized assistant for mobile recommendations. Your expertise lies in helping users find the best smartphones based on their preferences, budget, and feature requirements. 
    You have access to a comprehensive database of mobile devices, including their specifications, prices, and reviews. 

    When a user asks for a recommendation:
    - Understand their needs, such as budget, brand preference, storage, camera quality, or screen size.
    - Provide concise, accurate, and personalized recommendations based on the available mobile data.
    - If asked about specific features or comparisons, explain them clearly without unnecessary jargon.
    - Stay focused on mobile devices and related queries, and refrain from discussing unrelated topics.
    

    CONTEXT:
    {context}

    QUESTION: {input}

    YOUR ANSWER:

    """
    qa_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", PRODUCT_BOT_TEMPLATE),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}")
    ]
)
    question_answer_chain = create_stuff_documents_chain(model, qa_prompt)
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

    conversational_rag_chain = RunnableWithMessageHistory(
    rag_chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history",
    output_messages_key="answer",
)
    return conversational_rag_chain



if __name__ == "__main__":
   vstore = data_ingestion("done")
   conversational_rag_chain = generation(vstore)
   answer= conversational_rag_chain.invoke(
    {"input": "can you tell me the best bluetooth buds?"},
    config={
        "configurable": {"session_id": "pruthvik"}
    },  
)["answer"]
   print(answer)
   answer1= conversational_rag_chain.invoke(
    {"input": "what is my previous question?"},
    config={
        "configurable": {"session_id": "pruthvik"}
    },  # constructs a key "abc123" in `store`.
)["answer"]
   print(answer1)
