from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

class User(AbstractUser):
    ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('LIBRARIAN', 'Librarian'),
        ('STUDENT', 'Student'),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='STUDENT'
    )

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = 'ADMIN'
        if not self.role:
            self.role = 'STUDENT'
        super().save(*args, **kwargs)

    def is_admin(self):
        return self.role == 'ADMIN'

    def is_librarian(self):
        return self.role == 'LIBRARIAN'

    def is_student(self):
        return self.role == 'STUDENT'


class Book(models.Model):
    # Basic Information
    title = models.CharField(max_length=500)
    series = models.CharField(max_length=500, blank=True, null=True)
    author = models.CharField(max_length=500)
    
    # Ratings & Description
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    liked_percent = models.IntegerField(default=0, blank=True, null=True, help_text="Percentage of readers who liked this book")
    
    # Publishing Details
    language = models.CharField(max_length=100, default='English', blank=True, null=True)
    isbn = models.CharField(max_length=50, unique=True, blank=True, null=True)
    pages = models.IntegerField(default=0, blank=True, null=True)
    publisher = models.CharField(max_length=500, blank=True, null=True)
    publish_date = models.CharField(max_length=50, blank=True, null=True)
    
    # Categories & Awards
    genres = models.TextField(blank=True, null=True, help_text="Comma-separated genres")
    
    # Inventory
    quantity = models.PositiveIntegerField(default=1)
    
    # Cover Image
    cover_img = models.URLField(max_length=1000, blank=True, null=True)
    
    # Auto-updated timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['author']),
            models.Index(fields=['isbn']),
        ]
    
    def __str__(self):
        return self.title
    
    @property
    def is_available(self):
        return self.quantity > 0
    
    @property
    def genre_list(self):
        if self.genres:
            if self.genres.startswith('[') and self.genres.endswith(']'):
                import ast
                try:
                    return ast.literal_eval(self.genres)
                except:
                    return [g.strip() for g in self.genres.strip('[]').split(',')]
            return [g.strip() for g in self.genres.split(',')]
        return []
    

    @property
    def cover_url(self):
        """Return cover image URL or default placeholder"""
        return self.cover_img if self.cover_img else 'https://via.placeholder.com/300x450?text=No+Cover'


class BorrowRecord(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='borrow_records')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='borrow_records')
    borrow_date = models.DateTimeField(default=timezone.now)
    return_date = models.DateTimeField(null=True, blank=True)
    is_returned = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.student.username} - {self.book.title}"
    
    def has_pending_return_request(self):
        """Check if there's a pending return request for this borrow record"""
        try:
            return hasattr(self, 'return_request') and self.return_request.status == 'PENDING'
        except:
            return False


class ReturnRequest(models.Model):
    REQUEST_STATUS = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    borrow_record = models.OneToOneField(BorrowRecord, on_delete=models.CASCADE, related_name='return_request')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='return_requests')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='return_requests')
    request_date = models.DateTimeField(default=timezone.now)
    approved_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=REQUEST_STATUS, default='PENDING')
    librarian_notes = models.TextField(blank=True, null=True, help_text="Notes from librarian about book condition")
    
    class Meta:
        ordering = ['-request_date']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['request_date']),
        ]
    
    def __str__(self):
        return f"Return request for {self.book.title} by {self.student.username} - {self.status}"
    
    def approve(self, librarian, notes=None):
        self.status = 'APPROVED'
        self.approved_date = timezone.now()
        if notes:
            self.librarian_notes = notes
        self.save()
        
        # Update borrow record
        self.borrow_record.is_returned = True
        self.borrow_record.return_date = timezone.now()
        self.borrow_record.save()
        
        # Increase book quantity
        self.book.quantity += 1
        self.book.save()
    
    def reject(self, librarian, notes):
        """Reject the return request with reason"""
        self.status = 'REJECTED'
        self.librarian_notes = notes
        self.save()