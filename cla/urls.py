from django.urls import path
from . import views
from django.urls import path, include
from .views import (
    add_item, borrowed_items, item_detail, edit_item, 
    delete_item, move_item_to_collection, 
    add_comment, add_collection, edit_collection, 
    delete_collection, edit_comment, delete_comment, 
    manage_collections, collection_info, add_item_to_collection,
    remove_item_from_collection, request_borrow, manage_borrow_requests, 
    approve_borrow_request, reject_borrow_request, return_borrowed_item, manage_borrowed_items, send_reminder, request_access, approve_access, reject_access
)

urlpatterns = [
    path('', views.landing, name='landing'),
    path('sign-in', views.sign_in, name='sign_in'),
    path('sign-out', views.sign_out, name='sign_out'),
    path('auth-receiver', views.auth_receiver, name='auth_receiver'),
    path("guest-home/", views.guest_home, name="guest_home"),
    path('dashboard/', views.role_based_dashboard, name='role_based_dashboard'),
    path('dashboard/patron/', views.patron_dashboard, name='patron_dashboard'),
    path('dashboard/librarian/', views.librarian_dashboard, name='librarian_dashboard'),
    path('librarian/manage-users/', views.manage_users, name="manage_users"),
    path('change-role/<int:user_id>/<str:new_role>/', views.change_user_role, name='change_user_role'),
    path("profile/", views.profile_view, name="profile"),
    path("browse/", views.browse_equipment, name="browse_equipment"),

    path("item/<uuid:item_id>/", views.item_detail, name="item_detail"),
    path('item/<uuid:item_id>/edit/', edit_item, name='edit_item'),
    path('item/<uuid:item_id>/delete/', delete_item, name='delete_item'),
    path('item/<uuid:item_id>/move/', move_item_to_collection, name='move_item_to_collection'),
    path('item/add/', add_item, name='add_item'),

    path('collection/add/', add_collection, name='add_collection'),
    path('collection/<int:collection_id>/edit/', edit_collection, name='edit_collection'),
    path('collection/<int:collection_id>/delete/', delete_collection, name='delete_collection'),
    path('collections/manage/', manage_collections, name='manage_collections'),
    path('collection/<int:collection_id>/', collection_info, name='collection_info'),
    path("approve-access/<int:collection_id>/<int:user_id>/", approve_access, name="approve_access"),


    path('collection/<int:collection_id>/add-item/', add_item_to_collection, name='add_item_to_collection'),
    path('collection/<int:collection_id>/remove-item/<uuid:item_id>/', remove_item_from_collection, name='remove_item_from_collection'),
    path("request-access/<int:collection_id>/", request_access, name="request_access"),

    path('item/<uuid:item_id>/comment/', add_comment, name='add_comment'),
    path('comment/<int:comment_id>/edit/', edit_comment, name='edit_comment'),
    path('comment/<int:comment_id>/delete/', delete_comment, name='delete_comment'),

    path('item/<uuid:item_id>/gear_rating/', views.submit_gear_rating, name='submit_gear_rating'),
    path('gear_rating/<int:gear_rating_id>/edit/', views.edit_gear_rating, name='edit_gear_rating'),
    path('gear_rating/<int:gear_rating_id>/delete/', views.delete_gear_rating, name='delete_gear_rating'),

    path("item/<uuid:item_id>/request-borrow/", request_borrow, name="request_borrow"),
    path("librarian/manage-borrow-requests/", manage_borrow_requests, name="manage_borrow_requests"),
    path('manage-borrowed-items/', manage_borrowed_items, name='manage_borrowed_items'),
    path("librarian/borrow-request/<uuid:request_id>/approve/", approve_borrow_request, name="approve_borrow_request"),
    path("librarian/borrow-request/<uuid:request_id>/reject/", reject_borrow_request, name="reject_borrow_request"),
    path("librarian/borrow-request/<uuid:request_id>/return/", return_borrowed_item, name="return_borrowed_item"),
    path('requested-items/', views.view_requested_items, name='view_requested_items'),
    path('cancel-request/<uuid:request_id>/', views.cancel_borrow_request, name='cancel_borrow_request'),
    path("borrowed-items/", borrowed_items, name="borrowed_items"),
    path("return-item/<uuid:request_id>/", return_borrowed_item, name="return_borrowed_item"),
    path('patron/collections/', views.patron_collections, name='patron_collections'),
    path('guest/collections/', views.guest_collections, name='guest_collections'),
    path('send-reminder/<uuid:request_id>/', views.send_reminder, name='send_reminder'),
    path('select2/', include('django_select2.urls')), 
    path("reject-access/<int:collection_id>/<int:user_id>/", reject_access, name="reject_access"), 
    path("librarian/borrowed-items/", views.librarian_borrowed_items, name="librarian_borrowed_items"),
]