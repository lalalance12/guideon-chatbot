import logging
from query_skill_matcher import find_skill_and_knowledge_for_query, get_knowledge_for_query

# Configure logging
logging.basicConfig(level=logging.INFO)

def main():
    # Example query
    query = "How to develop secure software applications"
    
    print("Method 1: Get multiple matches with details")
    # Find matching skills and their underpinning knowledge
    matches = find_skill_and_knowledge_for_query(
        query_text=query,
        similarity_threshold=0.6,
        top_n=3  # Return top 3 matches
    )
    
    # Display results
    if matches:
        print(f"Top matches for query: '{query}'")
        for i, match in enumerate(matches, 1):
            print(f"\nMatch {i}:")
            print(f"Skill Title: {match['skill_title']}")
            print(f"Similarity Score: {match['similarity']:.4f}")
            print(f"Underpinning Knowledge:\n{match['underpinning_knowledge']}")
    else:
        print(f"No matches found for query: '{query}'")
    
    print("\n" + "-"*50 + "\n")
    
    print("Method 2: Simple convenience function for direct knowledge lookup")
    # Get the best matching knowledge directly
    result = get_knowledge_for_query(
        query_text=query,
        similarity_threshold=0.6
    )
    
    if result:
        print(f"Best match for query: '{query}'")
        print(f"Skill Title: {result['best_skill_title']}")
        print(f"Similarity Score: {result['similarity_score']:.4f}")
        print(f"Knowledge Text:\n{result['knowledge_text']}")
    else:
        print(f"No match found for query: '{query}'")

if __name__ == "__main__":
    main() 