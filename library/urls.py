from django.urls import path
from . import views


urlpatterns = [
    # Landing
    path('', views.login_view, name='login'),
    
    # Authentification
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard
    path('dashboard_redirect/', views.dashboard_redirect, name='dashboard_redirect'),
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('librarian_dashboard/', views.librarian_dashboard, name='librarian_dashboard'),
    path('student_dashboard/', views.student_dashboard, name='student_dashboard'),
    
    # Books
    path('books/', views.book_list, name='book_list'),
    path('books/add/', views.add_book, name='add_book'),
    path('books/edit/<int:book_id>/', views.edit_book, name='edit_book'),
    path('books/delete/<int:book_id>/', views.delete_book, name='delete_book'),
    
    # Borrow/Return 
    path('borrow/<int:book_id>/', views.borrow_book, name='borrow_book'),
    path('my-books/', views.my_borrowed_books, name='my_borrowed_books'),
    
    # Return Request URLs (Student)
    path('return/<int:borrow_id>/', views.return_book, name='return_book'),
    path('my-return-requests/', views.my_return_requests, name='my_return_requests'),
    path('cancel-request/<int:request_id>/', views.cancel_return_request, name='cancel_return_request'),
    
    # Return Request URLs (Librarian)
    path('librarian/manage-return/', views.manage_return_requests, name='manage_return_requests'),
    path('librarian/process-return/<int:request_id>/', views.process_return_request, name='process_return_request'),
    
    # Chatbot
    path('chatbot/', views.chatbot_page, name='chatbot_page'),
    path('chatbot/ask/', views.chatbot_ask, name='chatbot_ask'),
]
