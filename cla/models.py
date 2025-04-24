from django.utils import timezone
from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import boto3
import uuid
import os
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from datetime import timedelta
from django.core.mail import send_mail

def validate_image_file_extension(value):
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png']:
        raise ValidationError("Only JPG, JPEG, and PNG images are allowed.")

def validate_image_file_size(value):
    max_size = 5 * 1024 * 1024  # 5MB
    if value.size > max_size:
        raise ValidationError("Image file size must be 5MB or smaller.")

def validate_image(value):
    validate_image_file_extension(value)
    validate_image_file_size(value)


class User(AbstractUser):
    ROLE_CHOICES = [
        ('patron', 'Patron'),
        ('librarian', 'Librarian'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='patron')
    profile_picture = models.ImageField(
        upload_to='profilepics/',
        default='profilepics/default.jpg',
        blank=True,
        null=True,
        validators=[validate_image]
    )

    description = models.TextField(blank=True, default="")


    def get_profile_picture_url(self):
        if not self.profile_picture:
            return f"{settings.MEDIA_URL}profilepics/default.jpg"

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )

        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": str(self.profile_picture)},
            ExpiresIn=3600
        )
        return url


class Item(models.Model):
    STATUS_CHOICES = [
        ('checked_in', 'Checked In'),
        ('in_use', 'In Use'),
        ('in_repair', 'In Repair'),
        ('reserved', 'Reserved'), 
        ('lost', 'Lost'),
        ('on_hold', 'On Hold'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    identifier = models.CharField(max_length=50, unique=True, help_text="Unique key, barcode, QR code, ISBN, etc.")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='checked_in')
    location = models.CharField(max_length=255, help_text="Library location (e.g., Home Library, Work Library).")
    description = models.TextField(blank=True)

    image = models.ImageField(
        upload_to='item_images/',
        default='item_images/default_item.jpg',
        blank=True,
        null=True,
        validators=[validate_image]
    )

    collections = models.ManyToManyField('Collection', related_name='items_in_collection', blank=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_image_url(self):
        if not self.image or not self.image.name:
            return f"{settings.MEDIA_URL}item_images/tent.png"

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )

        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": str(self.image)},
            ExpiresIn=3600
        )
        return url

    def delete(self, *args, **kwargs):
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )

        if self.image and self.image.name != "item_images/default_item.jpg":
            try:
                s3_client.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=str(self.image))
            except Exception as e:
                print(f"Error deleting primary image from S3: {e}")

            # Delete extra images
        for img in self.extra_images.all():  # Fixed reference to extra_images
            try:
                s3_client.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=str(img.image))
            except Exception as e:
                print(f"Error deleting {img.image} from S3: {e}")
            img.delete()

        super().delete(*args, **kwargs)

    # chat gpt 4o reformatted, I added this to dynamically update browse equipment status column from calendar
    def get_status_on(self, check_date):
        for request in self.borrow_requests.filter(status="approved"):
            if request.borrow_date <= check_date <= request.due_date - timedelta(days=1):
                return "In Use"
            elif check_date == request.due_date:
                return "In Repair"
        return "Checked In"

    def __str__(self):
        return f"{self.id}: {self.title} ({self.identifier})"


class ItemImage(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="extra_images")
    image = models.ImageField(
        upload_to="item_images/",
        validators=[validate_image]
    )

    def get_image_url(self):
        if not self.image:
            return f"{settings.MEDIA_URL}item_images/default_item.jpg"

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )

        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": str(self.image)},
            ExpiresIn=3600
        )
        return url

    def __str__(self):
        return f"Extra image: {self.image.name}"

class Collection(models.Model):
    VISIBILITY_CHOICES = [
        ('public', 'Public'),
        ('private', 'Private'),
    ]

    title = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default='public')

    items = models.ManyToManyField('Item', related_name='collections_in', blank=True)
    allowed_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="private_collections",
        blank=True,
        help_text="Users allowed to access this private collection. Librarians can see all collections."
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="collections_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    access_requests = models.ManyToManyField(User, related_name="requested_collections", blank=True)


    def can_user_access(self, user):
        if self.visibility == "public":
            return True
        if user.is_authenticated:
            if user.role == "librarian":
                return True
            if self.allowed_users.filter(id=user.id).exists():
                return True
        return False

    def clean(self):
        if self.visibility == "private" and self.id != None:
            for item in self.items.all():
                if item.collections_in.filter(visibility="private").exclude(id=self.id).exists():
                    raise ValidationError(f"Item '{item.title}' is already in another private collection.")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.clean()

    def __str__(self):
        return f"{self.title} ({self.visibility})"
    
class Comment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    item = models.ForeignKey('Item', on_delete=models.CASCADE, related_name="comments")
    text = models.TextField()
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.rating}⭐️: {self.text}"

class GearConditionRating(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='gear_ratings')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(default=1)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class BorrowRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('returned', 'Returned'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="borrow_requests"
    )
    item = models.ForeignKey(
        Item, on_delete=models.CASCADE, related_name="borrow_requests"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    request_date = models.DateTimeField(auto_now_add=True)
    decision_date = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=255, default = "N/A")
    borrow_date = models.DateField()
    due_date = models.DateField()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


    def approve(self):
        """Approve the borrow request and update the item status."""
        self.status = "approved"
        self.decision_date = timezone.now()
        self.item.status = "reserved"
        self.item.save()
        self.save()

        # chat gpt 4o formatting, updating approve and reject methods to send notifications similar to librarians reminders for items due dates
        subject = f"Your Borrow Request for '{self.item.title}' Has Been Approved"
        message = (
            f"Hi {self.user.username},\n\n"
            f"Your request to borrow '{self.item.title}' has been approved.\n"
            f"You may borrow the item from {self.borrow_date} to {self.due_date}.\n\n"
            "Thanks!"
        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [self.user.email])

    def reject(self):
        """Reject the borrow request."""
        self.status = "rejected"
        self.decision_date = timezone.now()
        self.save()

        subject = f"Borrow Request for '{self.item.title}' Rejected"
        message = (
            f"Hi {self.user.username},\n\n"
            f"Unfortunately, your request to borrow '{self.item.title}' was rejected.\n"
            f"If you have questions, please contact a librarian.\n\n"
            "Thanks!"
        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [self.user.email])

    def return_item(self):
        """Mark the item as returned."""
        self.status = "returned"
        self.item.status = "checked_in"
        self.item.save()
        self.save()

    def __str__(self):
        return f"{self.user.username} requested {self.item.title} ({self.status})"