from store.db import get_chroma_connection

def test_search(query: str):
    print(f"\nSearching for: '{query}'")
    vector_store = get_chroma_connection()        
    results = vector_store.similarity_search(query, k=3)
    
    if not results:
        print("No results found.")
        return

    print(f"Success: Found {len(results)} exact legal matches.")

    for i, doc in enumerate(results):
        act = doc.metadata.get('act_name', 'Unknown Act')
        dapha = doc.metadata.get('dapha_no', 'N/A')
        chapter = doc.metadata.get('chapter', 'General')
        chunk = doc.metadata.get('chunk_id', 'N/A')

        print(f"\n Result {i+1}")
        print(f"Act:      {act}")
        print(f"Citation: Section (Dapha) {dapha} [Chapter: {chapter}]")
        print(f"Lineage:  ID: {chunk}")
        content = doc.page_content.replace('\n', ' ').strip()
        print(f"Snippet:  {content[:250]}")

if __name__ == "__main__":
    test_search("What are the penalties for driving without a license?")