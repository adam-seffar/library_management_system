# library/management/commands/import_books.py
import csv
import os
from django.core.management.base import BaseCommand
from django.db import IntegrityError
from library.models import Book

class Command(BaseCommand):
    help = 'Import books from output.csv file'
    
    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')
        parser.add_argument('--clear', action='store_true', help='Clear existing books before import')
    
    def handle(self, *args, **options):
        csv_path = options['csv_file']
        
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(f'File not found: {csv_path}'))
            return
        
        if options['clear']:
            Book.objects.all().delete()
            self.stdout.write(self.style.WARNING('Cleared all existing books'))
        
        with open(csv_path, 'r', encoding='utf-8') as file:
            # Detect delimiter (tab or comma)
            sample = file.read(1024)
            file.seek(0)
            delimiter = '\t' if '\t' in sample else ','
            
            reader = csv.DictReader(file, delimiter=delimiter)
            
            # Print columns found
            self.stdout.write(f"Columns found: {', '.join(reader.fieldnames)}")
            
            imported = 0
            skipped = 0
            errors = []
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 for header row
                try:
                    # Clean and prepare data
                    title = row.get('title', '').strip()
                    if not title:
                        self.stdout.write(self.style.WARNING(f"Row {row_num}: Skipped - No title"))
                        skipped += 1
                        continue
                    
                    # Check if book already exists by title and author
                    author = row.get('author', '').strip()
                    if Book.objects.filter(title=title, author=author).exists():
                        self.stdout.write(self.style.WARNING(f"Row {row_num}: Skipped - Book already exists: {title}"))
                        skipped += 1
                        continue
                    
                    # Parse rating (handle empty or invalid values)
                    rating = 0.00
                    try:
                        rating_val = row.get('rating', '0')
                        if rating_val:
                            rating = float(rating_val)
                    except (ValueError, TypeError):
                        rating = 0.00
                    
                    # Parse liked_percent
                    liked_percent = 0
                    try:
                        liked_val = row.get('likedPercent', '0')
                        if liked_val:
                            liked_percent = int(float(liked_val))
                    except (ValueError, TypeError):
                        liked_percent = 0
                    
                    # Parse pages
                    pages = 0
                    try:
                        pages_val = row.get('pages', '0')
                        if pages_val:
                            pages = int(pages_val)
                    except (ValueError, TypeError):
                        pages = 0
                    
                    # Handle publish date (various formats)
                    publish_date = row.get('publishDate', '').strip()
                    
                    # Handle ISBN (remove any non-numeric characters if needed)
                    isbn = row.get('isbn', '').strip()
                    if isbn == '0' or not isbn:
                        isbn = None
                    
                    # Create book
                    book = Book.objects.create(
                        title=title,
                        series=row.get('series', '').strip() or None,
                        author=author,
                        rating=rating,
                        description=row.get('description', '').strip() or None,
                        liked_percent=liked_percent,
                        language=row.get('language', 'English').strip() or 'English',
                        isbn=isbn,
                        pages=pages,
                        publisher=row.get('publisher', '').strip() or None,
                        publish_date=publish_date or None,
                        genres=row.get('genres', '').strip() or None,
                        cover_img=row.get('coverImg', '').strip() or None,
                        quantity=1  # Default quantity
                    )
                    
                    imported += 1
                    self.stdout.write(f"✓ Imported: {book.title} by {book.author}")
                    
                except IntegrityError as e:
                    errors.append(f"Row {row_num}: Integrity error - {str(e)}")
                    skipped += 1
                except Exception as e:
                    errors.append(f"Row {row_num}: Unexpected error - {str(e)}")
                    skipped += 1
            
            # Summary
            self.stdout.write(self.style.SUCCESS(f"\n✅ Import completed!"))
            self.stdout.write(f"   • Imported: {imported} books")
            self.stdout.write(f"   • Skipped: {skipped} books")
            
            if errors:
                self.stdout.write(self.style.WARNING(f"\n⚠️ Errors encountered:"))
                for error in errors[:10]:  # Show first 10 errors
                    self.stdout.write(f"   {error}")
                if len(errors) > 10:
                    self.stdout.write(f"   ... and {len(errors) - 10} more errors")