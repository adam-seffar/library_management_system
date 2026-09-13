from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .forms import RegisterForm, LoginForm
from .decorators import admin_required, librarian_required

from django.db.models import Q
from django.utils import timezone
from .models import Book, BorrowRecord
from .forms import BookForm


import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import ReturnRequest
from .forms import ReturnRequestForm, ApproveReturnForm
from django.contrib.admin.views.decorators import staff_member_required
from .rag_chatbot import get_chatbot_response
# ============ AUTHENTIFICATION ============

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Your account has been created !')
            login(request, user)
            return redirect('dashboard_redirect')
    else:
        form = RegisterForm()
    return render(request, 'authenticate/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('dashboard_redirect')
        else:
            messages.error(request, 'Invalid username or password')
    else:
        form = LoginForm()

    return render(request, 'authenticate/login.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')



# ============ DASHBOARD ============
def dashboard_redirect(request):
    user = request.user
    if user.is_authenticated:
        if user.is_admin():
            return redirect('admin_dashboard')
        elif user.is_librarian():
            return redirect('librarian_dashboard')
        else:
            return redirect('student_dashboard')
    else:
        return redirect('login')

@login_required
@admin_required
def admin_dashboard(request):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    total_books = Book.objects.count()
    # Calculate available books by summing quantities where quantity > 0
    available_books = sum(book.quantity for book in Book.objects.all())
    borrowed_books = BorrowRecord.objects.filter(is_returned=False).count()
    
    total_users = User.objects.count()
    total_students = User.objects.filter(role='STUDENT').count()
    total_librarians = User.objects.filter(role='LIBRARIAN').count()
    
    active_borrows = BorrowRecord.objects.filter(is_returned=False).count()
    
    # Recent borrow activity
    recent_borrows = BorrowRecord.objects.select_related('student', 'book').order_by('-borrow_date')[:10]
    
    context = {
        'total_books': total_books,
        'available_books': available_books,
        'borrowed_books': borrowed_books,
        'total_users': total_users,
        'total_students': total_students,
        'total_librarians': total_librarians,
        'active_borrows': active_borrows,
        'recent_borrows': recent_borrows,
    }
    
    return render(request, 'library/admin/dashboard.html', context)



@login_required
def student_dashboard(request):
    borrowed_books = BorrowRecord.objects.filter(
        student=request.user,
        is_returned=False
    ).select_related('book')
    
    #Calculate Dates
    for borrow in borrowed_books:
        borrow.due_date = borrow.borrow_date + timezone.timedelta(days=14)
        borrow.days_left = (borrow.due_date - timezone.now()).days
        borrow.has_pending_return_request = borrow.has_pending_return_request()
    
    return_history = BorrowRecord.objects.filter(
        student=request.user,
        is_returned=True
    ).select_related('book').order_by('-return_date')[:5]
    
    
    pending_returns = ReturnRequest.objects.filter(
        student=request.user,
        status='PENDING'
    ).select_related('book')
    
    total_returned = BorrowRecord.objects.filter(
        student=request.user,
        is_returned=True
    ).count()
    
    total_borrowed = borrowed_books.count()
    
    context = {
        'borrowed_books': borrowed_books,
        'return_history': return_history,
        'pending_returns': pending_returns,
        'total_returned': total_returned,
        'total_borrowed': total_borrowed,
        'can_borrow_more': total_borrowed < 3,
        'remaining_borrows': 3 - total_borrowed,
        'return_history_count': BorrowRecord.objects.filter(student=request.user, is_returned=True).count(),
    }
    
    return render(request, 'library/student/dashboard.html', context)


@login_required
@librarian_required
def librarian_dashboard(request):
    from django.contrib.auth import get_user_model
    from django.db.models import Count
    from datetime import timedelta
    
    User = get_user_model()
    
    all_books = Book.objects.all().order_by('-id')[:20]
    recent_books = Book.objects.all().order_by('-created_at')[:10]
    total_books = Book.objects.count()
    available_books = sum(book.quantity for book in Book.objects.all())
    
    # Borrowing stats
    active_borrows = BorrowRecord.objects.filter(is_returned=False).select_related('student', 'book')
    active_borrows_list = list(active_borrows)
    
    for borrow in active_borrows_list:
        borrow.due_date = borrow.borrow_date + timezone.timedelta(days=14)
        borrow.days_left = (borrow.due_date - timezone.now()).days
        borrow.is_overdue = borrow.days_left < 0
    
    # Overdue books
    overdue_books = [b for b in active_borrows_list if b.is_overdue]
    
    # Return requests
    pending_returns = ReturnRequest.objects.filter(status='PENDING').select_related('student', 'book', 'borrow_record')
    
    popular_books = Book.objects.annotate(
        borrow_count=Count('borrow_records')
    ).filter(borrow_count__gt=0).order_by('-borrow_count')[:5]
    
    recent_borrows = BorrowRecord.objects.select_related('student', 'book').order_by('-borrow_date')[:10]
    recent_returns = ReturnRequest.objects.filter(status='APPROVED').select_related('student', 'book').order_by('-approved_date')[:5]
    
    recent_activity = []
    
    for borrow in recent_borrows:
        recent_activity.append({
            'type': 'borrow',
            'student': borrow.student.username,  # Use 'student' consistently
            'action': 'borrowed',
            'book_title': borrow.book.title,
            'timestamp': borrow.borrow_date
        })
    
    for ret in recent_returns:
        recent_activity.append({
            'type': 'return',
            'student': ret.student.username,  # Use 'student' consistently
            'action': 'returned',
            'book_title': ret.book.title,
            'timestamp': ret.approved_date if ret.approved_date else ret.request_date
        })
    
    recent_activity.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activity = recent_activity[:10]
    
    unique_genres = set()
    for book in Book.objects.exclude(genres__isnull=True).exclude(genres=''):
        unique_genres.update(book.genre_list)
    
    context = {
        'all_books': all_books,
        'recent_books': recent_books,
        'total_books': total_books,
        'available_books': available_books,
        'total_students': User.objects.filter(role='STUDENT').count(),
        'active_borrows': active_borrows_list[:10],
        'active_borrows_count': len(active_borrows_list),
        'pending_returns': pending_returns[:5],
        'pending_returns_count': pending_returns.count(),
        'overdue_books_count': len(overdue_books),
        'unique_genres_count': len(unique_genres),
        'popular_books': popular_books,
        'recent_activity': recent_activity,
    }
    
    return render(request, 'library/librarian/dashboard.html', context)


# ============ BOOKS CURD ============


@login_required
def book_list(request):
    query = request.GET.get('q', '')
    
    if query:
        books = Book.objects.filter(
            Q(title__icontains=query) | 
            Q(author__icontains=query)
        )
    else:
        books = Book.objects.all()
    
    user_borrowed_ids = []
    if request.user.is_student():
        user_borrowed_ids = BorrowRecord.objects.filter(
            student=request.user,
            is_returned=False
        ).values_list('book_id', flat=True)
    
    return render(request, 'library/books/book_list.html', {
        'books': books, 
        'query': query,
        'user_borrowed_ids': list(user_borrowed_ids)  
    })


@login_required
@librarian_required
def add_book(request):
    if request.method == 'POST':
        form = BookForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Book added successfully!')
            return redirect('book_list')
    else:
        form = BookForm()
    
    return render(request, 'library/books/add_book.html', {'form': form})


@login_required
@librarian_required
def edit_book(request, book_id):
    """Edit book details (Librarian/Admin only)"""
    book = get_object_or_404(Book, id=book_id)
    
    if request.method == 'POST':
        form = BookForm(request.POST, instance=book)
        if form.is_valid():
            form.save()
            messages.success(request, f'✅ "{book.title}" updated successfully!')
            return redirect('book_list')
    else:
        form = BookForm(instance=book)
    
    return render(request, 'library/books/edit_book.html', {
        'form': form, 
        'book': book
    })


@login_required
@librarian_required
def delete_book(request, book_id):
    """Delete book (Librarian/Admin only)"""
    book = get_object_or_404(Book, id=book_id)
    
    if request.method == 'POST':
        book_title = book.title
        book.delete()
        messages.success(request, f'✅ "{book_title}" removed from library!')
        return redirect('book_list')
    
    return render(request, 'library/books/delete_book.html', {'book': book})

# ============ BORROW/RETURN SYSTEM ============

@login_required
def borrow_book(request, book_id):
    
    if not request.user.is_student():
        messages.error(request, 'Only students can borrow books!')
        return redirect('book_list')
    
    book = get_object_or_404(Book, id=book_id)
    
    if not book.is_available:  
        messages.error(request, f'❌ No copies of "{book.title}" are available!')
        return redirect('book_list')
    
    existing_borrow = BorrowRecord.objects.filter(
        student=request.user, 
        book=book, 
        is_returned=False
    ).exists()
    
    if existing_borrow:
        messages.error(request, f'❌ You already have "{book.title}" borrowed!')
        return redirect('book_list')
    
    active_borrows = BorrowRecord.objects.filter(
        student=request.user, 
        is_returned=False
    ).count()
    
    if active_borrows >= 3:
        messages.error(request, '❌ You can only borrow up to 3 books at a time!')
        return redirect('book_list')
    
    BorrowRecord.objects.create(
        student=request.user,
        book=book
    )
    book.quantity -= 1 
    book.save()
    
    messages.success(request, f'✅ You borrowed "{book.title}" successfully!')
    return redirect('student_dashboard')


@login_required
def return_book(request, borrow_id):
    
    borrow_record = get_object_or_404(
        BorrowRecord, 
        id=borrow_id, 
        student=request.user,
        is_returned=False
    )
    
    if ReturnRequest.objects.filter(borrow_record=borrow_record, status='PENDING').exists():
        messages.error(request, f'❌ You already have a pending return request for "{borrow_record.book.title}". Please wait for librarian approval.')
        return redirect('student_dashboard')
    
    return_request = ReturnRequest.objects.create(
        borrow_record=borrow_record,
        student=request.user,
        book=borrow_record.book
    )
    
    messages.success(request, f'✅ Return request submitted for "{borrow_record.book.title}". The librarian will review and approve it.')
    return redirect('student_dashboard')


@login_required
def my_return_requests(request):
    """Student views their pending return requests"""
    pending_requests = ReturnRequest.objects.filter(
        student=request.user,
        status='PENDING'
    ).select_related('book', 'borrow_record')
    
    approved_requests = ReturnRequest.objects.filter(
        student=request.user,
        status='APPROVED'
    ).select_related('book', 'borrow_record')[:10]
    
    rejected_requests = ReturnRequest.objects.filter(
        student=request.user,
        status='REJECTED'
    ).select_related('book', 'borrow_record')[:10]
    
    context = {
        'pending_requests': pending_requests,
        'approved_requests': approved_requests,
        'rejected_requests': rejected_requests,
    }
    
    return render(request, 'library/student/return_requests.html', context)


@login_required
@librarian_required
def manage_return_requests(request):
    """Librarian views all pending return requests"""
    pending_requests = ReturnRequest.objects.filter(
        status='PENDING'
    ).select_related('student', 'book', 'borrow_record').order_by('request_date')
    
    approved_requests = ReturnRequest.objects.filter(
        status='APPROVED'
    ).select_related('student', 'book')[:20]
    
    rejected_requests = ReturnRequest.objects.filter(
        status='REJECTED'
    ).select_related('student', 'book')[:20]
    
    context = {
        'pending_requests': pending_requests,
        'approved_requests': approved_requests,
        'rejected_requests': rejected_requests,
        'total_pending': pending_requests.count(),
    }
    
    return render(request, 'library/librarian/manage_return.html', context)


@login_required
@librarian_required
def process_return_request(request, request_id):
    """Librarian approves or rejects a return request"""
    return_request = get_object_or_404(ReturnRequest, id=request_id, status='PENDING')
    
    if request.method == 'POST':
        form = ApproveReturnForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            notes = form.cleaned_data['notes']
            
            if action == 'approve':
                # Approve the return
                return_request.approve(request.user, notes)
                messages.success(
                    request, 
                    f'✅ Return approved for "{return_request.book.title}" by {return_request.student.username}.'
                )
            else:
                # Reject the return
                return_request.reject(request.user, notes)
                messages.warning(
                    request,
                    f'⚠️ Return rejected for "{return_request.book.title}". Reason: {notes}'
                )
            
            return redirect('manage_return_requests')
    else:
        form = ApproveReturnForm()
    
    # Calculate days borrowed for context
    days_borrowed = (timezone.now() - return_request.borrow_record.borrow_date).days
    
    context = {
        'return_request': return_request,
        'form': form,
        'days_borrowed': days_borrowed,
    }
    
    return render(request, 'library/librarian/process_return.html', context)


@login_required
def cancel_return_request(request, request_id):
    """Student cancels a pending return request"""
    return_request = get_object_or_404(
        ReturnRequest,
        id=request_id,
        student=request.user,
        status='PENDING'
    )
    
    if request.method == 'POST':
        book_title = return_request.book.title
        return_request.delete()
        messages.success(request, f'✅ Return request for "{book_title}" has been cancelled.')
        return redirect('my_return_requests')
    
    return render(request, 'library/student/cancel_return.html', {'return_request': return_request})

@login_required
def my_borrowed_books(request):
    borrowed_books = BorrowRecord.objects.filter(
        student=request.user,
        is_returned=False
    ).select_related('book')
    
    return render(request, 'library/student/borrowed_books.html', {
        'borrowed_books': borrowed_books
    })
    
    
# ============ CHATBOT ============

@login_required
def chatbot_page(request):
    return render(request, 'library/chatbot.html', {'now': timezone.now()})

@login_required
@require_http_methods(["POST"])
def chatbot_ask(request):
    import json
    
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            query = data.get('query', '').strip()
        except:
            query = request.POST.get('query', '').strip()
    else:
        query = request.POST.get('query', '').strip()
    
    if not query:
        return JsonResponse({'response': ' Please ask a question about books, library rules, or your account.'})
    
    try:
        response = get_chatbot_response(request.user, query)
    except Exception as e:
        print(f"Chatbot error: {e}")
        import traceback
        traceback.print_exc()
        response = "Sorry, I encountered an error. Please try again."
    
    return JsonResponse({'response': response})