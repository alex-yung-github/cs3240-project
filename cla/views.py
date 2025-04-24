import os
import boto3
import logging
import datetime
from datetime import date
from django import forms
from django.utils import timezone
from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth import login, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from cla.models import Item, Comment, ItemImage
from .models import GearConditionRating
from django.db.models import Count, Prefetch, Q 
from django.core.exceptions import ValidationError
from datetime import date
from django.core.mail import send_mail
from datetime import timedelta
from django.shortcuts import redirect, get_object_or_404
from .models import BorrowRequest

from google.oauth2 import id_token
from google.auth.transport import requests

from .models import BorrowRequest, Item, Collection, Comment
from .forms import ItemForm, CollectionForm, CommentForm

from mysite.settings import IS_HEROKU_APP, MEDIA_URL

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ["title", "identifier", "status", "location", "description", "image"]

logger = logging.getLogger(__name__)
User = get_user_model()

def landing(request):
    user = "Guest"
    if request.user:
        user = request.user
    print(user)
    return render(request, 'landing.html', {'user': request.user})

@csrf_exempt
def sign_in(request):
    is_production = IS_HEROKU_APP
    auth_url = (
        'https://swe-s25-project-a-06-ec1a6da2a3f8.herokuapp.com/auth-receiver'
        if is_production
        else 'http://localhost:8000/auth-receiver'
    )
    return render(request, 'sign-in.html', {'auth_url': auth_url})


from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import UserProfileForm
import boto3
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings


@login_required
def profile_view(request):
    """Render and handle updates to the profile page."""
    if request.method == "POST":
        user = request.user

        # Handle text fields updates
        user.first_name = request.POST.get("first_name", user.first_name)
        user.last_name = request.POST.get("last_name", user.last_name)
        user.description = request.POST.get("description", user.description)

        # Handle profile picture if uploaded
        if request.FILES.get("profile_picture"):
            file = request.FILES["profile_picture"]
            file_path = f"profilepics/{user.id}/{file.name}"

            # Delete old profile picture if not the default
            if user.profile_picture and user.profile_picture.name != "profilepics/default.jpg":
                try:
                    s3_client = boto3.client(
                        "s3",
                        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                        region_name=settings.AWS_S3_REGION_NAME
                    )
                    s3_client.delete_object(
                        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                        Key=str(user.profile_picture)
                    )
                except Exception as e:
                    print(f"Error deleting old profile picture: {e}")

            # Save new profile picture
            default_storage.save(file_path, ContentFile(file.read()))
            user.profile_picture = file_path

        # Save user changes
        user.save()

    return render(request, "dashboards/profile.html")

@csrf_exempt
def auth_receiver(request):
    """
    Google calls this URL after the user has signed in with their Google account.
    """
    logger.info("Auth receiver called")

    token = request.POST.get('credential')  
    if not token:
        logger.error("No credential token received in the request")
        return HttpResponse("No token provided", status=403)

    try:
        user_data = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
        )
        now = datetime.datetime.now(datetime.timezone.utc)
        issued_at = datetime.datetime.fromtimestamp(user_data['iat'], datetime.timezone.utc)
        expires_at = datetime.datetime.fromtimestamp(user_data['exp'], datetime.timezone.utc)

        # got time sync error, llow up to 5 seconds of clock skew
        clock_skew_tolerance = datetime.timedelta(seconds=5)
        if not (issued_at - clock_skew_tolerance <= now <= expires_at + clock_skew_tolerance):
            return HttpResponse("Token timing is invalid", status=403)

    except ValueError as e:
        return HttpResponse(f"Invalid token: {e}", status=403)

    except ValueError as e:
        logger.error(f"Token verification failed: {e}")
        return HttpResponse(f"Invalid token: {e}", status=403)


    email = user_data['email']
    first_name = user_data.get('given_name', '')
    last_name = user_data.get('family_name', '')

    user, created = User.objects.get_or_create(username=email, defaults={
        'email': email,
        'first_name': first_name,
        'last_name': last_name,
        'role': 'patron',
        'profile_picture': 'profilepics/default.jpg'
    })

    if created:
        logger.info(f"Created new user: {user.username} with role {user.role}")
    else:
        logger.info(f"Existing user logged in: {user.username}")

    login(request, user)

    return redirect('role_based_dashboard')


def sign_out(request):
    request.session.flush()
    return redirect('landing')


def guest_home(request):
    request.session["is_guest"] = True  # Store guest session
    return render(request, "dashboards/guest-home.html")

def role_based_dashboard(request):
    # print(request.user)
    # print(request.user.role)
    if request.user.is_authenticated:
        if request.user.role == 'librarian':
            return redirect('librarian_dashboard')
        elif request.user.role == 'patron':
            return redirect('patron_dashboard')
    return redirect('guest_home')

def patron_dashboard(request):
    return render(request, 'dashboards/patron_dashboard.html', {'user': request.user, 'is_patron': True})

def is_librarian(user):
    return user.role == 'librarian'

def is_patron(user):
    return user.role == 'patron'

@login_required
@user_passes_test(is_librarian)
def librarian_dashboard(request):
    return render(request, 'dashboards/librarian_dashboard.html', {'user': request.user, 'is_librarian': True})

@login_required
@user_passes_test(is_librarian)
def manage_users(request):
    all_users = User.objects.all()
    return render(request, 'dashboards/manage_users.html', {'user': request.user, 'all_users': all_users, 'is_librarian': True})

@login_required
@user_passes_test(is_librarian)
def change_user_role(request, user_id, new_role):
    user = get_object_or_404(User, id=user_id)

    if request.user == user and new_role == "patron":
        messages.error(request, "You cannot demote yourself to a patron.", extra_tags='librarian_manage')
        return redirect('manage_users')

    if user.role == new_role:
        messages.warning(request, f"{user.username} is already a {new_role}.", extra_tags='librarian_manage')
    else:
        if user.role == 'librarian':
            user_collections = Collection.objects.filter(created_by=user)
            for user_collection in user_collections:
                user_collection.visibility = "public"

        user.role = new_role
        user.save()
        messages.success(request, f"{user.username} is now a {new_role}.", extra_tags='librarian_manage')

    return redirect('manage_users')

def item_detail(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    is_private_collection = item.collections.filter(visibility='private').exists()

    borrow_requests = BorrowRequest.objects.filter(item=item, status="approved")


    # Check if the item is in a private collection
    if item.collections.exists():
        collection = item.collections.first()
        if collection.visibility == "private":
            if not request.user.is_authenticated or request.user.role == "guest":
                messages.error(request, "You do not have permission to view this item.", extra_tags='item')
                return redirect('browse_equipment')

    return render(request, "items_and_collections/item_detail.html", {"item": item, "borrow_requests": borrow_requests, "is_private_collection": is_private_collection})

# add Item
@login_required
@user_passes_test(is_librarian)
def add_item(request):
    if request.user.role != "librarian":
        messages.error(request, "You do not have permission to add items.", extra_tags='item')
        return redirect('browse_equipment')

    if request.method == "POST":
        form = ItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.added_by = request.user
            item.save()
            form.save_m2m()  # Save Many-to-Many relationships
            extra_images = request.FILES.getlist('extra_images')
            for image in extra_images:
                print("Adding image", image)
                ItemImage.objects.create(item=item, image=image)

            messages.success(request, "Item added successfully!", extra_tags='item')
            return redirect('browse_equipment')
    else:
        form = ItemForm()

    return render(request, "items_and_collections/item_form.html", {"form": form, "action": "Add Item"})

# edit Item
@login_required
@user_passes_test(is_librarian)
def edit_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    if request.user.role != "librarian":
        messages.error(request, "You do not have permission to edit items.", extra_tags='item')
        return redirect('browse_equipment')

    if request.method == 'POST':
        form = ItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()

            # Handle additional images upload
            extra_images = request.FILES.getlist('extra_images')
            for image in extra_images:
                print("Adding image", image)
                ItemImage.objects.create(item=item, image=image)

            # Handle deletion of extra images
            for key in request.POST:
                if key.startswith('delete_image_'):
                    image_id = key.split('_')[-1]
                    try:
                        image = ItemImage.objects.get(id=image_id, item=item)
                        # Delete the image from S3 if necessary
                        if image.image:
                            s3_client = boto3.client(
                                "s3",
                                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                                region_name=settings.AWS_S3_REGION_NAME
                            )
                            s3_client.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=str(image.image))
                        image.delete()
                    except ItemImage.DoesNotExist:
                        pass

            messages.success(request, "Item updated successfully!", extra_tags='item')
            return redirect('browse_equipment')
    else:
        form = ItemForm(instance=item)


    extra_images = item.extra_images.all()
    return render(request, "items_and_collections/item_form.html", {
        "form": form,
        "action": "Save Edit",
        "object": item,
        "extra_images": extra_images
    })
# delete Item
@login_required
@user_passes_test(is_librarian)
def delete_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    if request.user.role != "librarian":
        messages.error(request, "You do not have permission to delete items.", extra_tags='item')
        return redirect('browse_equipment')

    item.delete()
    messages.success(request, "Item deleted successfully!", extra_tags='item')
    return redirect('browse_equipment')

# edit Collection
@login_required
@user_passes_test(is_librarian)
def edit_collection(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)
    if request.user.role != "librarian":
        messages.error(request, "You do not have permission to edit collections.", extra_tags='collection')
        return redirect('manage_collections')

    if request.method == "POST":
        form = CollectionForm(request.POST, instance=collection)
        if form.is_valid():
            form.save()
            messages.success(request, "Collection updated successfully!", extra_tags='collection')
            return redirect('manage_collections')
    else:
        form = CollectionForm(instance=collection)

    return render(request, "items_and_collections/collection_form.html", {"form": form, "action": "Edit Collection"})

# delete Collection
@login_required
@user_passes_test(is_librarian)
def delete_collection(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)
    if request.user.role != "librarian":
        messages.error(request, "You do not have permission to delete collections.", extra_tags='collection')
        return redirect('manage_collections')

    collection.delete()
    messages.success(request, "Collection deleted successfully!", extra_tags='collection')
    return redirect('manage_collections')

@login_required
def move_item_to_collection(request, item_id):
    item = get_object_or_404(Item, id=item_id)

    user = request.user
    # Determine which collections the user can see
    if user.role == "librarian":
        collections = Collection.objects.all()
    else:
        collections = Collection.objects.filter(
            visibility="public"
        ).exclude(
            created_by__in=User.objects.filter(role="librarian")
        )

    if request.method == "POST":
        selected_collection_ids = request.POST.getlist("collection_id")
        selected_collections = Collection.objects.filter(id__in=selected_collection_ids)

        # Check if any selected collection is private
        private_collections = selected_collections.filter(visibility="private")
        public_collections = selected_collections.filter(visibility="public")


        if private_collections.count() > 1:
            messages.error(request, "An item can only belong to one private collection at a time.")
            return redirect("move_item_to_collection", item_id=item.id)

        if private_collections.exists():
            # If adding to a private collection, remove from all public collections
            item.collections.remove(*item.collections.filter(visibility="public"))

            # If already in a private collection, confirm with the user
            existing_private = item.collections.filter(visibility="private").exclude(id__in=selected_collections)
            if existing_private.exists():
                messages.warning(request, f"Item is already in a private collection: {existing_private.first().title}. "
                                          f"Moving will remove it from the current private collection.")

        # Update collections
        if selected_collections.count() > 0:
            item.collections.set(selected_collections)
            collections_containing_item = collections.filter(items=item)
            collections_containing_item_not_selected = collections_containing_item.exclude(
                id__in=selected_collection_ids)
            for collection in collections_containing_item_not_selected:
                collection.items.remove(item)
            for collection in selected_collections:
                collection.items.add(item)
            item.save()
            messages.success(request, "Item successfully moved to the selected collection(s).")
            return redirect("item_detail", item_id=item.id)
        else:
            item.collections.clear()
            item.save()
            collections_containing_item = collections.filter(
                items=item
            )
            for collection in collections_containing_item:
                collection.items.remove(item)
            return redirect("item_detail", item_id=item.id)

    return render(request, "items_and_collections/move_item.html", {
        "item": item,
        "collections": collections,
    })

@login_required
@user_passes_test(is_patron)
def add_comment(request, item_id):
    item = get_object_or_404(Item, id=item_id)

    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.user = request.user
            comment.item = item
            comment.save()
            return redirect("item_detail", item_id=item.id)
    else:
        form = CommentForm()

    return render(request, "add_comment.html", {"form": form, "item": item})


@login_required
def edit_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)

    # added a check if the logged-in user is the comment owner
    if request.user != comment.user:
        messages.error(request, "You do not have permission to edit this comment.", extra_tags='comment')
        return redirect('item_detail', item_id=comment.item.id)

    if request.method == "POST":
        # Using a simplified approach - directly updating model fields
        rating = request.POST.get('rating')
        text = request.POST.get('text')

        if rating and text:
            comment.rating = rating
            comment.text = text
            comment.save()
            messages.success(request, "Comment updated successfully.", extra_tags='comment')
        else:
            messages.error(request, "Please provide both rating and text.", extra_tags='comment')

        return redirect('item_detail', item_id=comment.item.id)

    # If not a POST request, use the original form approach
    else:
        form = CommentForm(instance=comment)
        return render(request, "items_and_collections/edit_comment.html", {"form": form, "comment": comment})


@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)

    # only the comment owner or a librarian can delete
    if request.user != comment.user and request.user.role != "librarian":
        messages.error(request, "You do not have permission to delete this comment.", extra_tags='comment')
        return redirect('item_detail', item_id=comment.item.id)

    item_id = comment.item.id  # save item ID before deleting
    comment.delete()
    messages.success(request, "Comment deleted successfully.", extra_tags='comment')
    return redirect('item_detail', item_id=item_id)

def browse_equipment(request):
    """Display items based on user role with filtering options."""
    from django.db.models import Q

    if request.user.is_authenticated:
        if request.user.role == "librarian":
            # Librarians see all items
            items = Item.objects.all()
        else:
            # Patrons don't see all items
            items = Item.objects.filter(
                Q(collections__visibility="public") | Q(collections__visibility="private", collections__allowed_users=request.user) | Q(collections=None)
            ).distinct()
    else:
        items = Item.objects.filter(
                Q(collections__visibility="public") | Q(collections=None)
            ).distinct()

    print("Items being sent to template:")
    for item in items:
        print(f"{item.title} - Collections: {[col.title for col in item.collections.all()]}")

    title_filter = request.GET.get('title', '')
    location_filter = request.GET.get('location', '')
    identifier_filter = request.GET.get('identifier', '')
    collection_filter = request.GET.get('collection', '')

    if title_filter:
        items = items.filter(title__icontains=title_filter)
    
    if location_filter:
        items = items.filter(location__icontains=location_filter)
    
    if identifier_filter:
        items = items.filter(identifier__icontains=identifier_filter)
    
    if collection_filter:
        items = items.filter(collections__title__icontains=collection_filter)

    collections = Collection.objects.all()

    visible_collections = []

    for collection in collections:
        if collection.can_user_access(request.user):
            collection.user_can_access = True
            visible_collections.append(collection)
        else:
            collection.user_can_access = False
            if request.user.is_authenticated and request.user.role != "guest":
                visible_collections.append(collection)

    items = items.annotate(comment_count=Count('comments')).prefetch_related(
        Prefetch('comments', queryset=Comment.objects.order_by('-created_at'))
    )

    # chat gpt 4o reformatted, this section means future borrow requests aren't blocked 
    requested_items = set()
    borrowed_items = set()

    if request.user.is_authenticated:
        today = date.today()

        # Only mark as "Borrow Requested" if there's a PENDING request that overlaps today or in the future
        requested_items = set(
            BorrowRequest.objects.filter(
                user=request.user,
                status="pending",
                borrow_date__lte=today,
                due_date__gte=today
            ).values_list("item_id", flat=True)
        )

        borrowed_items = set(
            BorrowRequest.objects.filter(
                user=request.user,
                status="approved",
                borrow_date__lte=today,
                due_date__gte=today
            ).values_list("item_id", flat=True)
        )


    print("requested_items:", requested_items)
    print("borrowed_items (active today):", borrowed_items)

    for item in items:
        item.dynamic_status = item.get_status_on(date.today())

    context = {
        "items": items,
        "collections": visible_collections,
        "filters": {
            "title": title_filter,
            "location": location_filter,
            "identifier": identifier_filter,
            "collection": collection_filter
        },
        "requested_items": requested_items,
        "borrowed_items": borrowed_items,
    }

    return render(request, "browse_equipment.html", context)

@login_required
@user_passes_test(is_librarian)
def manage_collections(request):
    """Page to list and manage all collections with search functionality."""
    # Get search parameters
    title_filter = request.GET.get('title', '')
    keyword_filter = request.GET.get('keyword', '')
    
    # Base query - librarians can see all collections
    collections_query = Collection.objects.all()
    
    # Apply filters if provided
    if title_filter:
        collections_query = collections_query.filter(title__icontains=title_filter)
    
    if keyword_filter:
        collections_query = collections_query.filter(
            Q(description__icontains=keyword_filter) | 
            Q(items__title__icontains=keyword_filter) |
            Q(items__description__icontains=keyword_filter)
        ).distinct()
    
    context = {
        "collections": collections_query,
        "filters": {
            "title": title_filter,
            "keyword": keyword_filter
        }
    }
    
    return render(request, "items_and_collections/manage_collections.html", context)

def collection_info(request, collection_id):
    """View collection details and manage items with search functionality."""
    collection = get_object_or_404(Collection, id=collection_id)
    
    # Get search parameters
    title_filter = request.GET.get('title', '')
    keyword_filter = request.GET.get('keyword', '')
    
    # Check permissions (librarians can see all, patrons only public or their own)
    if request.user.is_authenticated:
        if request.user.role == 'patron':
            if collection.visibility != 'public' and not collection.allowed_users.filter(id=request.user.id).exists():
                messages.error(request, "You do not have permission to view this collection.", extra_tags='collection')
                return redirect('patron_collections')
    else:
        if collection.visibility != 'public':
            messages.error(request, "You do not have permission to view this collection.", extra_tags='collection')
            return redirect('guest_collections')
    
    # Determine if user can edit this collection
    if request.user.is_authenticated and (request.user.role == 'librarian' or collection.created_by == request.user):
        can_edit = True
    else:
        can_edit = False
    
    # Get items in this collection
    items = collection.items.all()
    
    # Apply filters if provided
    if title_filter:
        items = items.filter(title__icontains=title_filter)
    
    if keyword_filter:
        items = items.filter(
            Q(description__icontains=keyword_filter) |
            Q(identifier__icontains=keyword_filter) |
            Q(location__icontains=keyword_filter)
        ).distinct()
    
    # calculate items that can be added to this collection
    if can_edit:
        # start with all items
        all_items_query = Item.objects.all()
        
        # get IDs of items already in this collection
        items_in_collection_ids = collection.items.values_list('id', flat=True)
        
        if collection.visibility == 'public':
            # for public collections, exclude items that are already in this collection or any private collection
            items_in_private_collections_ids = Item.objects.filter(
                collections__visibility='private'
            ).values_list('id', flat=True)
            
            items_that_can_be_added = all_items_query.exclude(
                id__in=items_in_collection_ids
            ).exclude(
                id__in=items_in_private_collections_ids
            ).distinct()
        else:
            # for private collections, just exclude items already in this collection
            items_that_can_be_added = all_items_query.exclude(
                id__in=items_in_collection_ids
            ).distinct()
    else:
        items_that_can_be_added = Item.objects.none()

    context = {
        "collection": collection,
        "items": items,
        "items_that_can_be_added": items_that_can_be_added,
        "can_edit": can_edit,
        "filters": {
            "title": title_filter,
            "keyword": keyword_filter
        }
    }
    
    return render(request, "items_and_collections/collection_info.html", context)

@login_required
def add_item_to_collection(request, collection_id):
    """Add an item to a collection with permission checking for patrons and librarians"""
    collection = get_object_or_404(Collection, id=collection_id)
    
    # Check if the user has permission to modify this collection
    if request.user.role != 'librarian' and collection.created_by != request.user:
        messages.error(request, "You do not have permission to modify this collection.", extra_tags='collection')
        return redirect('collection_info', collection_id=collection.id)
    
    if request.method == "POST":
        item_id = request.POST.get("item_id")
        item = get_object_or_404(Item, id=item_id)
        
        try:
            if collection.visibility == 'private':
                messages.warning(
                    request,
                    "This collection is private. The item will be removed from all other collections.",
                    extra_tags='collection'
                )
                #remove items from other collections
                other_collections = item.collections.exclude(id=collection.id)
                for other_collection in other_collections:
                    other_collection.items.remove(item)
                    item.collections.remove(other_collection)

            #add the item to the collection
            collection.items.add(item)
            item.collections.add(collection)
            messages.success(request, f"{item.title} added to {collection.title}.")
        except ValidationError as e:
            messages.error(request, str(e), extra_tags='collection')
        
    return redirect("collection_info", collection_id=collection.id)

@login_required
def remove_item_from_collection(request, collection_id, item_id):
    """Remove an item from a collection with permission checking for patrons and librarians"""
    collection = get_object_or_404(Collection, id=collection_id)
    item = get_object_or_404(Item, id=item_id)
    
    # Check if the user has permission to modify this collection
    if request.user.role != 'librarian' and collection.created_by != request.user:
        messages.error(request, "You do not have permission to modify this collection.", extra_tags='collection')
        return redirect('collection_info', collection_id=collection.id)
    
    collection.items.remove(item)
    messages.success(request, f"{item.title} removed from {collection.title}.")
    return redirect("collection_info", collection_id=collection.id)

# chat gpt 4o debugged was always blocking a week of time on calendar no matter how much time selected
@login_required
def request_borrow(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    borrow_requests = BorrowRequest.objects.filter(item=item, status="approved")

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")

        if start_date and end_date:
            start_date = timezone.datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date = timezone.datetime.strptime(end_date, "%Y-%m-%d").date()

            # Key Fix: Set due date as end_date + 1 day ONLY
            due_date = end_date + timedelta(days=1)

            # Enforce max 7 day borrow
            if (end_date - start_date).days > 6:
                messages.error(request, "You can only borrow for up to 7 days.")
                return redirect("request_borrow", item_id=item.id) 
            
            conflicting_requests = BorrowRequest.objects.filter(
                item=item,
                status="approved",
                borrow_date__lt=due_date,
                due_date__gt=start_date
            )
            
            if conflicting_requests.exists():
                messages.error(request, "This item is already reserved for that time period.")
                return redirect("request_borrow", item_id=item.id)

            borrow_request = BorrowRequest.objects.create(
                user=request.user,
                item=item,
                borrow_date=start_date,
                due_date=due_date,
                reason=reason,
                status="pending"
            )

            # if the user is a librarian, automatically approve the request
            if request.user.role == 'librarian':
                borrow_request.approve() 
                
                overlapping_requests = BorrowRequest.objects.filter(
                    item=item,
                    status="pending",
                    borrow_date__lt=due_date,
                    due_date__gt=start_date
                ).exclude(id=borrow_request.id) 
                
                for overlap in overlapping_requests:
                    if overlap.due_date > due_date:
                        # adjust the borrow date to start after this request ends
                        original_borrow = overlap.borrow_date
                        original_due = overlap.due_date
                        
                        overlap.borrow_date = due_date
                        overlap.save()
                        
                        # notify the user about the changed dates
                        subject = f"Your Borrow Request for '{overlap.item.title}' Has Been Modified"
                        message = (
                            f"Hi {overlap.user.username},\n\n"
                            f"Your request to borrow '{overlap.item.title}' from "
                            f"{original_borrow.strftime('%B %d, %Y')} to {original_due.strftime('%B %d, %Y')} "
                            f"has been modified due to another approved request.\n\n"
                            f"The item is now available for you starting {overlap.borrow_date.strftime('%B %d, %Y')} "
                            f"until {overlap.due_date.strftime('%B %d, %Y')}.\n\n"
                            f"This request is still pending and requires librarian approval. If you no longer wish to "
                            f"borrow this item for the modified dates, you can cancel the request.\n\n"
                            "Thank you for your understanding.\n"
                            f"If you have questions, please contact a librarian.\n\n"
                            "Thanks!"
                        )
                        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [overlap.user.email])
                    else:
                        overlap.reject("A librarian has approved another request that conflicts with yours.")
                
                messages.success(request, f"Your borrow request for '{item.title}' has been automatically approved.")
            else:
                messages.success(request, "Your borrow request has been submitted.")
            return redirect("browse_equipment")

    return render(request, "borrow_requests/borrow_request_form.html", {
        "item": item,
        "borrow_requests": borrow_requests
    })


@login_required
@user_passes_test(is_librarian)
def manage_borrow_requests(request):
    """Librarians can view and manage borrow requests, with filtering."""
    borrow_requests = BorrowRequest.objects.select_related("user", "item").order_by("-request_date")

    item_filter = request.GET.get("item", "")
    user_filter = request.GET.get("user", "")
    status_filter = request.GET.get("status", "")

    if item_filter:
        borrow_requests = borrow_requests.filter(item__title__icontains=item_filter)
    if user_filter:
        borrow_requests = borrow_requests.filter(user__username__icontains=user_filter)
    if status_filter:
        borrow_requests = borrow_requests.filter(status=status_filter)

    context = {
        "borrow_requests": borrow_requests,
        "filters": {
            "item": item_filter,
            "user": user_filter,
            "status": status_filter,
        }
    }
    return render(request, "borrow_requests/manage_borrow_requests.html", context)

@login_required
@user_passes_test(is_librarian)
def approve_borrow_request(request, request_id):
    """ Approve a borrow request and update item status. """
    borrow_request = get_object_or_404(BorrowRequest, id=request_id)

    if borrow_request.status != "pending":
        messages.warning(request, "This request has already been processed.")
        return redirect("manage_borrow_requests")

    borrow_request.approve()
    messages.success(request, f"Approved borrow request for {borrow_request.item.title}.") 
    
    # the following was overlap request implementation was used with assistance from claude 3.7 sonnet
    overlapping_requests = BorrowRequest.objects.filter(
        item=borrow_request.item,
        status="pending",
        borrow_date__lt=borrow_request.due_date,
        due_date__gt=borrow_request.borrow_date
    ).exclude(id=borrow_request.id) 
    
    for overlapping_request in overlapping_requests: 
        if overlapping_request.due_date > borrow_request.due_date: 
            original_borrow_date = overlapping_request.borrow_date
            original_due_date = overlapping_request.due_date 
            
            overlapping_request.borrow_date = borrow_request.due_date
            overlapping_request.save() 
            
            # notify the user about the modified dates
            subject = f"Your Borrow Request for '{overlapping_request.item.title}' Has Been Modified"
            message = (
                f"Hi {overlapping_request.user.username},\n\n"
                f"Your request to borrow '{overlapping_request.item.title}' from "
                f"{original_borrow_date.strftime('%B %d, %Y')} to {original_due_date.strftime('%B %d, %Y')} "
                f"has been modified due to another approved request.\n\n"
                f"The item is now available for you starting {overlapping_request.borrow_date.strftime('%B %d, %Y')} "
                f"until {overlapping_request.due_date.strftime('%B %d, %Y')}.\n\n"
                f"This request is still pending and requires librarian approval. If you no longer wish to "
                f"borrow this item for the modified dates, you can cancel the request.\n\n"
                "Thank you for your understanding.\n"
                f"If you have questions, please contact a librarian.\n\n"
                "Thanks!"
            )
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [overlapping_request.user.email])
        else:
            # if this completely overlaps then simply just reject 
            overlapping_request.reject()
    
    return redirect("manage_borrow_requests")


@login_required
@user_passes_test(is_librarian)
def reject_borrow_request(request, request_id):
    """ Reject a borrow request. """
    borrow_request = get_object_or_404(BorrowRequest, id=request_id)

    if borrow_request.status != "pending":
        messages.warning(request, "This request has already been processed.")
        return redirect("manage_borrow_requests")

    borrow_request.reject()
    messages.error(request, f"Rejected borrow request for {borrow_request.item.title}.")
    return redirect("manage_borrow_requests")

@login_required
def view_requested_items(request):
    """Display all borrow requests made by the patron."""
    requests = BorrowRequest.objects.filter(user=request.user).order_by('-request_date')
    return render(request, "borrow_requests/view_requested_items.html", {"requests": requests})

@login_required
def cancel_borrow_request(request, request_id):
    """Allow users to cancel their borrow request if it's still pending."""
    borrow_request = BorrowRequest.objects.get(id=request_id, user=request.user)
    if borrow_request.status == "pending":
        borrow_request.delete()
    return redirect("view_requested_items")

@login_required
def borrowed_items(request):
    """Display the items currently borrowed by the user."""
    borrowed_items = BorrowRequest.objects.filter(user=request.user, status="approved")

    items_with_days_remaining = []

    for item in borrowed_items:
        days_remaining = (item.due_date - date.today()).days if item.due_date else None
        items_with_days_remaining.append({
            'item': item,
            'days_remaining': days_remaining,
        })

    return render(
        request,
        "borrow_requests/borrowed_items.html",
        {
            "borrowed_items": items_with_days_remaining,
            "today": date.today(),
        }
    ) 
    
@login_required
@user_passes_test(is_librarian)
def librarian_borrowed_items(request):
    """Display the items currently borrowed by the librarian."""
    borrowed_items = BorrowRequest.objects.filter(user=request.user, status="approved")

    items_with_days_remaining = []

    for item in borrowed_items:
        days_remaining = (item.due_date - date.today()).days if item.due_date else None
        items_with_days_remaining.append({
            'item': item,
            'days_remaining': days_remaining,
        })

    return render(
        request,
        "borrow_requests/librarian_borrowed_items.html",
        {
            "borrowed_items": items_with_days_remaining,
            "today": date.today(),
        }
    )

@login_required
def return_borrowed_item(request, request_id):
    """Allow a patron to return a borrowed item."""
    borrow_request = get_object_or_404(BorrowRequest, id=request_id, user=request.user, status="approved")

    if borrow_request.user != request.user and request.user.role != "librarian":
        messages.error(request, "You don't have permission to return this item.")
        return redirect("borrowed_items")
    
    if borrow_request.status == "approved":
        borrow_request.return_item()
        messages.success(request, f"'{borrow_request.item.title}' has been returned successfully!")
    
    # Redirect based on user role
    if request.user.role == "librarian":
        return redirect("librarian_borrowed_items")
    else:
        return redirect("borrowed_items")

@login_required
def submit_gear_rating(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    if request.method == 'POST':
        rating = int(request.POST.get('gear_rating'))
        comment = request.POST.get('gear_comment', '')
        GearConditionRating.objects.create(
            item=item,
            user=request.user,
            rating=rating,
            comment=comment
        )
        return redirect('item_detail', item_id=item.id)

# chat gpt 4o helped format the 2 functions below when getting a no reverse error when testing locally
@login_required
def edit_gear_rating(request, gear_rating_id):
    gear_rating = get_object_or_404(GearConditionRating, id=gear_rating_id)

    if request.user != gear_rating.user:
        messages.error(request, "You do not have permission to edit this gear rating.", extra_tags='gear_rating')
        return redirect('item_detail', item_id=gear_rating.item.id)

    if request.method == "POST":
        rating = int(request.POST.get('gear_rating'))
        comment = request.POST.get('gear_comment')

        if rating and comment:
            gear_rating.rating = rating
            gear_rating.comment = comment
            gear_rating.save()
            messages.success(request, "Gear condition rating updated successfully.", extra_tags='gear_rating')
        else:
            messages.error(request, "Please provide both rating and comment.", extra_tags='gear_rating')

        return redirect('item_detail', item_id=gear_rating.item.id)

    # If not a POST request, use the original template approach
    return render(request, "items_and_collections/edit_gear_rating.html", {"gear_rating": gear_rating})


@login_required
def delete_gear_rating(request, gear_rating_id):
    gear_rating = get_object_or_404(GearConditionRating, id=gear_rating_id)

    if request.user != gear_rating.user and request.user.role != "librarian":
        messages.error(request, "You do not have permission to delete this gear rating.", extra_tags='gear_rating')
        return redirect('item_detail', item_id=gear_rating.item.id)

    item_id = gear_rating.item.id 
    gear_rating.delete()
    messages.success(request, "Gear condition rating deleted successfully.", extra_tags='gear_rating')
    return redirect('item_detail', item_id=item_id)

@login_required
@user_passes_test(is_patron)
def patron_collections(request):
    """View and manage collections for patrons with search functionality"""
    # Get search parameters
    title_filter = request.GET.get('title', '')
    keyword_filter = request.GET.get('keyword', '')
    
    # Base queries
    public_collections_query = Collection.objects.filter(visibility='public')
    private_collections_query = Collection.objects.filter(visibility='private')
    my_collections_query = Collection.objects.filter(created_by=request.user)
    
    # Apply filters if provided
    if title_filter:
        public_collections_query = public_collections_query.filter(title__icontains=title_filter)
        private_collections_query = private_collections_query.filter(title__icontains=title_filter)
        my_collections_query = my_collections_query.filter(title__icontains=title_filter)
    
    if keyword_filter:
        public_collections_query = public_collections_query.filter(
            Q(description__icontains=keyword_filter) | 
            Q(items__title__icontains=keyword_filter) |
            Q(items__description__icontains=keyword_filter)
        ).distinct()
        
        private_collections_query = private_collections_query.filter(
            Q(description__icontains=keyword_filter)
        ).distinct()  # Only filter private collections by description, not items
        
        my_collections_query = my_collections_query.filter(
            Q(description__icontains=keyword_filter) | 
            Q(items__title__icontains=keyword_filter) |
            Q(items__description__icontains=keyword_filter)
        ).distinct()
    
    context = {
        "public_collections": public_collections_query,
        "my_collections": my_collections_query,
        "private_collections": private_collections_query,
        "filters": {
            "title": title_filter,
            "keyword": keyword_filter
        }
    }
    
    return render(request, "items_and_collections/patron_collections.html", context)

@login_required
def request_access(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)

    # Prevent duplicate requests
    if request.user in collection.access_requests.all():
        messages.warning(request, "You have already requested access.")
    else:
        collection.access_requests.add(request.user)
        messages.success(request, "Access request sent.")

    return redirect("patron_collections")

@login_required
def approve_access(request, collection_id, user_id):
    collection = get_object_or_404(Collection, id=collection_id)
    user = get_object_or_404(User, id=user_id)

    if user in collection.access_requests.all():
        collection.access_requests.remove(user)
        collection.allowed_users.add(user)
        messages.success(request, f"{user.username} has been granted access to {collection.title}.")
    else:
        messages.warning(request, "Invalid access request.")

    return redirect("manage_collections") 

def guest_collections(request):
    """View collections for guests with search functionality"""
    # Get search parameters
    title_filter = request.GET.get('title', '')
    keyword_filter = request.GET.get('keyword', '')
    
    # Base query - guests can only see public collections
    public_collections_query = Collection.objects.filter(visibility='public')
    
    # Apply filters if provided
    if title_filter:
        public_collections_query = public_collections_query.filter(title__icontains=title_filter)
    
    if keyword_filter:
        public_collections_query = public_collections_query.filter(
            Q(description__icontains=keyword_filter) | 
            Q(items__title__icontains=keyword_filter) |
            Q(items__description__icontains=keyword_filter)
        ).distinct()
    
    context = {
        "public_collections": public_collections_query,
        "filters": {
            "title": title_filter,
            "keyword": keyword_filter
        }
    }
    
    return render(request, "items_and_collections/guest_collections.html", context)


@login_required
def add_collection(request):
    """Add a new collection with permission handling for patrons and librarians"""
    if request.method == "POST":
        # For patrons, ensure visibility is set to public
        if request.user.role == 'patron':
            form = CollectionForm(request.POST, user=request.user)
        else:
            form = CollectionForm(request.POST)
            
        if form.is_valid():
            try:
                collection = form.save(commit=False)
                collection.created_by = request.user
                
                # Force public visibility for patrons
                if request.user.role == 'patron':
                    collection.visibility = 'public'
                    
                collection.save()
                form.save_m2m()
                
                messages.success(request, "Collection added successfully!", extra_tags='collection')
                
                # Redirect based on user role
                if request.user.role == 'librarian':
                    return redirect('manage_collections')
                else:
                    return redirect('patron_collections')
            except ValidationError as e:
                form.add_error(None, e)
    else:
        form = CollectionForm(user=request.user)

    return render(request, "items_and_collections/collection_form.html", {"form": form, "action": "Add Collection", "user": request.user})


@login_required
def manage_borrowed_items(request):
    borrowed_items = BorrowRequest.objects.filter(status="approved").select_related('user', 'item')

    items_with_days_remaining = []

    for item in borrowed_items:
        days_remaining = (item.due_date - date.today()).days if item.due_date else None
        items_with_days_remaining.append({
            'item': item,
            'days_remaining': days_remaining,
        })

    context = {
        "borrowed_items": items_with_days_remaining,
    }
    return render(request, "borrow_requests/manage_borrowed_items.html", context)

@login_required
def send_reminder(request, request_id):
    borrow_request = get_object_or_404(BorrowRequest, id=request_id)

    subject = f"Reminder: Your borrowed item '{borrow_request.item.title}'"
    message = (
        f"Hello {borrow_request.user.username},\n\n"
        f"This is a reminder that you have borrowed '{borrow_request.item.title}'.\n"
        f"Due Date: {borrow_request.due_date.strftime('%Y-%m-%d')}\n"
        "Please return it by the due date.\n\n"
        "Thank you!"
    )
    recipient_list = [borrow_request.user.email]

    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)
    print("sent reminder")

    return redirect('manage_borrowed_items') 

@login_required
def reject_access(request, collection_id, user_id): #this function was written similarly to what was writtin for the approve_access function but removes users from the access requests and rejects their request
    collection = get_object_or_404(Collection, id=collection_id)
    user = get_object_or_404(User, id=user_id)

    if user in collection.access_requests.all():
        collection.access_requests.remove(user)
        messages.success(request, f"Access request from {user.username} for {collection.title} has been rejected.")
    else:
        messages.warning(request, "Invalid access request.")

    return redirect("manage_collections") 

@login_required
def cancel_borrow_request(request, request_id):
    borrow_request = get_object_or_404(BorrowRequest, id=request_id, user=request.user)
    
    # identifies if the user has the authority to cancel such request 
    if borrow_request.user != request.user and request.user.role != "librarian":
        messages.error(request, "You don't have permission to cancel this request.")
        return redirect("borrowed_items")
    
    if borrow_request.status == "approved" and borrow_request.borrow_date > date.today():
        # if approved but not yet borrowed (future borrow date)
        borrow_request.status = "returned" 
        borrow_request.item.status = "checked_in"
        borrow_request.item.save()
        borrow_request.save()
        messages.success(request, f"Request for '{borrow_request.item.title}' has been canceled.")
    elif borrow_request.status == 'pending':
        borrow_request.delete() 
        messages.success(request, f"Request for '{borrow_request.item.title}' has been canceled.")
    
    if request.user.role == "librarian":
        if request.path.startswith('/librarian'):
            return redirect("librarian_borrowed_items")
        else:
            return redirect("view_requested_items")
    else:
        return redirect("view_requested_items")