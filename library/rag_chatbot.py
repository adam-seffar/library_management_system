# library/rag_chatbot.py
import json
import os
from pathlib import Path
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from sentence_transformers import SentenceTransformer
import chromadb

class RAGChatbot:
    
    def __init__(self, user):
        self.user = user
        self.model = None
        self.chroma_client = None
        self.book_collection = None
        self.rules_collection = None
        self.init_chromadb()
    
    def init_chromadb(self):
        
        try:
            print("Loading embedding model...")
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            
            db_path = Path(settings.BASE_DIR) / 'chroma_db'
            db_path.mkdir(exist_ok=True)
            
            self.chroma_client = chromadb.PersistentClient(path=str(db_path))
            
            self.book_collection = self.chroma_client.get_or_create_collection(
                name="library_books"
            )
            
            self.rules_collection = self.chroma_client.get_or_create_collection(
                name="library_rules"
            )
            
            self.ensure_data_loaded()
            
        except Exception as e:
            print(f"ChromaDB init error: {e}")
    
    def ensure_data_loaded(self):
        try:
            if self.book_collection.count() == 0:
                self.load_books_from_json()
            
            if self.rules_collection.count() == 0:
                self.load_rules_from_file()
        except Exception as e:
            print(f"Data loading error: {e}")
    
    def load_books_from_json(self):
        json_path = Path(settings.BASE_DIR) / 'book_dataset.json'
        
        if not json_path.exists():
            print(f"ERROR: {json_path} not found. Cannot load books.")
            return
        
        with open(json_path, 'r', encoding='utf-8') as f:
            books = json.load(f)
        
        documents = []
        metadatas = []
        ids = []
        
        for i, book in enumerate(books):
            doc_text = f"""Title: {book.get('title', 'Unknown')}
Author: {book.get('author', 'Unknown')}
Series: {book.get('series', 'Standalone')}
Rating: {book.get('rating', 'N/A')}/5
Description: {book.get('description', 'No description available')}
Genres: {book.get('genres', 'Various')}
Pages: {book.get('pages', 'N/A')}
Language: {book.get('language', 'English')}
Publisher: {book.get('publisher', 'Unknown')}"""
            
            documents.append(doc_text)
            metadatas.append({
                'title': book.get('title', ''),
                'author': book.get('author', ''),
                'rating': float(book.get('rating', 0)) if book.get('rating') else 0,
                'genres': book.get('genres', ''),
                'source': 'book_dataset'
            })
            ids.append(f"book_{i}")
        
        self.book_collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        print(f"Loaded {len(documents)} books from book_dataset.json into RAG system")
    
    def load_rules_from_file(self):
        rules_path = Path(settings.BASE_DIR) / 'library_rules.txt'
        
        if not rules_path.exists():
            print(f"ERROR: {rules_path} not found. Cannot load rules.")
            return
        
        with open(rules_path, 'r', encoding='utf-8') as f:
            rules_text = f.read()
        
        rule_sections = self.split_rules_into_sections(rules_text)
        
        documents = []
        metadatas = []
        ids = []
        
        for i, (title, content) in enumerate(rule_sections.items()):
            doc_text = f"{title}\n{content}"
            documents.append(doc_text)
            metadatas.append({
                'section': title,
                'source': 'library_rules'
            })
            ids.append(f"rule_{i}")
        
        self.rules_collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        print(f"Loaded {len(rule_sections)} rule sections from library_rules.txt into RAG system")
    
    def split_rules_into_sections(self, rules_text):
        sections = {}
        current_title = "General Rules"
        current_content = []
        
        for line in rules_text.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            if (line.isupper() or line.endswith(':')) and len(line) < 50:
                if current_content:
                    sections[current_title] = '\n'.join(current_content)
                current_title = line.rstrip(':')
                current_content = []
            else:
                current_content.append(line)
        
        if current_content:
            sections[current_title] = '\n'.join(current_content)
        
        return sections
    
    def get_user_context(self):
        from .models import BorrowRecord
        
        try:
            borrowed = BorrowRecord.objects.filter(
                student=self.user,
                is_returned=False
            ).select_related('book')
        except Exception as e:
            print(f"Error getting user context: {e}")
            borrowed = []
        
        context = f"""
USER INFORMATION:
- Name: {self.user.username}
- Role: {self.user.role}
- Total books borrowed: {borrowed.count() if hasattr(borrowed, 'count') else 0}/3
"""
        
        if borrowed and hasattr(borrowed, 'exists') and borrowed.exists():
            context += "\nCURRENTLY BORROWED BOOKS:\n"
            for record in borrowed:
                due_date = record.borrow_date + timedelta(days=14)
                days_left = (due_date - timezone.now()).days
                context += f"  - {record.book.title} by {record.book.author} (Due in {days_left} days)\n"
        else:
            context += "\nNo books currently borrowed.\n"
        
        return context
    
    def search_books(self, query, top_k=5):
        try:
            if self.book_collection.count() == 0:
                print("No books in collection")
                return {'documents': [[]], 'metadatas': [[]], 'distances': [[]]}
            
            query_embedding = self.model.encode([query]).tolist()
            
            results = self.book_collection.query(
                query_embeddings=query_embedding,
                n_results=top_k
            )
            return results
        except Exception as e:
            print(f"Book search error: {e}")
            return {'documents': [[]], 'metadatas': [[]], 'distances': [[]]}
    
    def search_rules(self, query, top_k=3):
        try:
            if self.rules_collection.count() == 0:
                print("No rules in collection")
                return {'documents': [[]], 'metadatas': [[]]}
            
            query_embedding = self.model.encode([query]).tolist()
            
            results = self.rules_collection.query(
                query_embeddings=query_embedding,
                n_results=top_k
            )
            return results
        except Exception as e:
            print(f"Rules search error: {e}")
            return {'documents': [[]], 'metadatas': [[]]}
    
    def get_book_recommendations(self, query, top_k=5):
        results = self.search_books(query, top_k)
        
        if not results.get('documents') or not results['documents'] or not results['documents'][0]:
            return []
        
        recommendations = []
        for i, doc in enumerate(results['documents'][0]):
            if results.get('metadatas') and results['metadatas'] and len(results['metadatas'][0]) > i:
                metadata = results['metadatas'][0][i]
            else:
                metadata = {}
            recommendations.append({
                'title': metadata.get('title', 'Unknown'),
                'author': metadata.get('author', 'Unknown'),
                'rating': metadata.get('rating', 0),
            })
        
        return recommendations
    
    def format_book_recommendations(self, recommendations):
        if not recommendations:
            return "I couldn't find any books matching your request. Try being more specific about genres or authors!"
        
        response = "📚 **Here are some recommendations:**\n\n"
        for i, book in enumerate(recommendations[:3], 1):
            response += f"{i}. **{book['title']}** by {book['author']}\n"
            if book['rating'] > 0:
                response += f"   ⭐ Rating: {book['rating']}/5\n"
            response += "\n"
        
        return response
    
    def answer_with_context(self, query, book_results, rule_results, user_context):
        query_lower = query.lower()
        
        #recommendations
        if any(word in query_lower for word in ['recommend', 'suggest', 'what should i read', 'looking for']):
            recommendations = self.get_book_recommendations(query, 5)
            return self.format_book_recommendations(recommendations)
        
        # borrowing limit
        if any(word in query_lower for word in ['how many', 'borrow limit', 'maximum books']):
            from .models import BorrowRecord
            try:
                borrowed = BorrowRecord.objects.filter(student=self.user, is_returned=False).count()
                remaining = 3 - borrowed
                return f" You can borrow up to **3 books** at a time.\n\nYou currently have **{borrowed}** book(s) borrowed.\nYou can borrow **{remaining}** more book(s)."
            except:
                return " You can borrow up to **3 books** at a time. The loan period is 14 days."
        
        # due dates
        if any(word in query_lower for word in ['due date', 'when to return', 'return date', 'due']):
            from .models import BorrowRecord
            try:
                borrowed = BorrowRecord.objects.filter(student=self.user, is_returned=False).select_related('book')
                
                if not borrowed.exists():
                    return " You don't have any books borrowed right now."
                
                response = " **Your due dates:**\n\n"
                for record in borrowed:
                    due_date = record.borrow_date + timedelta(days=14)
                    days_left = (due_date - timezone.now()).days
                    status = "⚠️ OVERDUE!" if days_left < 0 else f"{days_left} days left"
                    response += f"• **{record.book.title}** - Due: {due_date.strftime('%B %d, %Y')} ({status})\n"
                
                return response
            except Exception as e:
                print(f"Error getting due dates: {e}")
                pass
        
        # library hours
        if any(word in query_lower for word in ['hour', 'open', 'timing', 'when is library']):
            rules_results = self.search_rules("library hours", 1)
            if rules_results.get('documents') and rules_results['documents'] and rules_results['documents'][0]:
                return rules_results['documents'][0][0]
            return "🏛️ **Library Hours:**\n\n• Monday - Friday: 9:00 AM - 8:00 PM\n• Saturday: 10:00 AM - 6:00 PM\n• Sunday: Closed"
        
        # specific book
        if any(word in query_lower for word in ['tell me about', 'information about', 'details of', 'what is']):
            words = query_lower.split()
            stop_words = ['tell', 'me', 'about', 'information', 'details', 'of', 'what', 'is']
            search_term = ' '.join([w for w in words if w not in stop_words])
            
            if len(search_term) > 2:
                specific_results = self.search_books(search_term, 1)
                
                if specific_results.get('documents') and specific_results['documents'] and specific_results['documents'][0]:
                    if specific_results.get('metadatas') and specific_results['metadatas'] and len(specific_results['metadatas'][0]) > 0:
                        metadata = specific_results['metadatas'][0][0]
                    else:
                        metadata = {}
                    doc = specific_results['documents'][0][0]
                    
                    response = f"📖 **{metadata.get('title', 'Unknown')}**\n\n"
                    lines = doc.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('Title:'):
                            response += f"{line}\n"
                    return response
        
        # Use retrieved book information
        if book_results.get('documents') and book_results['documents'] and book_results['documents'][0]:
            response = " **Here's what I found:**\n\n"
            for i, doc in enumerate(book_results['documents'][0][:2]):
                if book_results.get('metadatas') and book_results['metadatas'] and len(book_results['metadatas'][0]) > i:
                    metadata = book_results['metadatas'][0][i]
                else:
                    metadata = {}
                response += f"**{metadata.get('title', 'Book')}** by {metadata.get('author', 'Unknown')}\n"
                
                # Extract key info from document
                lines = doc.split('\n')
                for line in lines[:5]:
                    line = line.strip()
                    if 'Rating:' in line:
                        response += f"{line}\n"
                    elif 'Genres:' in line:
                        response += f"{line}\n"
                    elif 'Description:' in line and len(line) > 20:
                        response += f"{line[:200]}...\n"
                response += "\n"
            
            return response
        
        if rule_results.get('documents') and rule_results['documents'] and rule_results['documents'][0]:
            response = "📋 **Library Information:**\n\n"
            response += rule_results['documents'][0][0][:500]
            return response
        
        return "I'm not sure about that. Try asking about:\n• Book recommendations\n• Borrowing limits\n• Due dates\n• Library hours\n• Specific book information"
    
    def process_query(self, query):
        """Main method to process user query"""
        if not query or not query.strip():
            return "Please ask a question about books, library rules, or your account."
        
        try:
            # Get user context
            user_context = self.get_user_context()
            
            # Search for relevant books
            book_results = self.search_books(query, top_k=3)
            
            # Search for relevant rules
            rule_results = self.search_rules(query, top_k=2)
            
            # Generate answer
            answer = self.answer_with_context(query, book_results, rule_results, user_context)
            
            return answer
        except Exception as e:
            print(f"Process error: {e}")
            import traceback
            traceback.print_exc()
            return "Sorry, I encountered an error. Please try again."


def get_chatbot_response(user, query):
    # Create a new instance for each request
    chatbot = RAGChatbot(user)
    return chatbot.process_query(query)