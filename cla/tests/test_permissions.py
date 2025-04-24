from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test.utils import override_settings
from cla.models import Collection, Item, Comment

User = get_user_model()

@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class UserPermissionsTests(TestCase):
    def setUp(self):
        self.librarian = User.objects.create_user(username='librarian', password='librarianpass', role="librarian")
        self.patron = User.objects.create_user(username='patron', password='patronpass', role="patron")
        self.patron_2 = User.objects.create_user(username='malicious_patron', password='password', role='patron')

        self.client.login(username='librarian', password='librarianpass')  
        response = self.client.get(reverse('add_item')) 
        print("Librarian Login Test: ", response.status_code)  

        self.item = Item.objects.create(
            title='Test Item',
            identifier='12345',
            status='checked_in',
            location='Main Library',
            description='Test Description',
            added_by=self.librarian
        )

        self.collection = Collection.objects.create(
            title='Test Collection',
            description='Test Collection Description',
            visibility='public',
            created_by=self.librarian
        )

        self.comment = Comment.objects.create(
            user=self.patron,
            item=self.item,
            text="This is a comment.",
            rating=4
        )

    def test_librarian_can_edit_item(self):
        self.client.login(username='librarian', password='librarianpass')
        response = self.client.post(reverse('edit_item', args=[self.item.id]), {
            'title': 'Updated Item', 
            'identifier': self.item.identifier,
            'status': self.item.status,
            'location': self.item.location,
            'description': 'Updated Description'}) #requires all fields to be filled for successful post
        self.assertEqual(response.status_code, 302) #(redirected successfully)
        self.item.refresh_from_db()
        self.assertEqual(self.item.title, 'Updated Item') #successfully updated item

    def test_patron_cannot_edit_item(self):
        self.client.login(username='patron', password='patronpass')
        response = self.client.post(reverse('edit_item', args=[self.item.id]), {
            'title': 'Hacked Item', 
            'identifier': self.item.identifier,
            'status': self.item.status,
            'location': self.item.location,
            'description': 'Hacked Description'
            })
        self.assertEqual(response.status_code, 302) #redirect success
        self.item.refresh_from_db()
        self.assertEqual(self.item.title, 'Test Item') #check item was not updated

    def test_guest_cannot_edit_item(self):
        self.client.session.flush()
        response = self.client.post(reverse('edit_item', args=[self.item.id]), {
            'title': 'Hacked Item', 
            'identifier': self.item.identifier,
            'status': self.item.status,
            'location': self.item.location,
            'description': 'Hacked Description'
            })
        self.assertEqual(response.status_code, 302) #redirect success
        self.item.refresh_from_db()
        self.assertEqual(self.item.title, 'Test Item') #check item was not updated

    def test_librarian_can_add_item(self):
        self.client.login(username='librarian', password='librarianpass')  
        response = self.client.post(reverse('add_item'), {
            'title': 'New Item',
            'identifier': '12345',
            'status': 'checked_in',
            'location': 'Main Library',
            'description': 'New Description',
            'added_by': self.librarian.id
        })
        self.assertEqual(response.status_code, 200) # 
        self.assertTrue(Item.objects.filter(identifier='12345').exists()) #check item added
        
    def test_guest_cannot_add_item(self):
        self.client.session.flush()
        response = self.client.post(reverse('add_item'), {
            'title': 'Unauthorized Item',
            'identifier': '99999',
            'status': 'checked_in',
            'location': 'Main Library',
            'description': 'This should not be added'
        })
        self.assertEqual(response.status_code, 302) #redirected successfully
        self.assertFalse(Item.objects.filter(identifier='99999').exists()) #check item not added

    def test_patron_cannot_add_item(self):
        self.client.login(username='patron', password='patronpass')
        response = self.client.post(reverse('add_item'), {
            'title': 'Unauthorized Item',
            'identifier': '88888',
            'status': 'checked_in',
            'location': 'Main Library',
            'description': 'This should not be added'
        })
        self.assertEqual(response.status_code, 302) #redirected successfully
        self.assertFalse(Item.objects.filter(identifier='88888').exists()) #check item not added

    def test_librarian_can_add_collection(self):
        self.client.login(username='librarian', password='librarianpass')
        response = self.client.post(reverse('add_collection'), {
            'title': 'New Collection',
            'description': 'Test Description',
            'visibility': 'public'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Collection.objects.filter(title='New Collection').exists())

    # def test_patron_cannot_add_collection(self):
    #     self.client.login(username='patron', password='patronpass')
    #     response = self.client.post(reverse('add_collection'), {'title': 'Unauthorized Collection'})
    #     self.assertEqual(response.status_code, 302)
    #     self.assertFalse(Collection.objects.filter(title='Unauthorized Collection').exists())

    def test_guest_cannot_add_collection(self):
        self.client.session.flush()
        response = self.client.post(reverse('add_collection'), {'title': 'Unauthorized Collection'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Collection.objects.filter(title='Unauthorized Collection').exists())

    def test_librarian_can_edit_collection(self):
        self.client.login(username='librarian', password='librarianpass')
        response = self.client.post(reverse('edit_collection', args=[self.collection.id]), {
            'title': 'Updated Collection',
            'description': 'Updated Description',
            'visibility': 'private'
        })
        self.assertEqual(response.status_code, 302)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.title, 'Updated Collection')

    def test_patron_cannot_edit_collection(self):
        self.client.login(username='patron', password='patronpass')
        response = self.client.post(reverse('edit_collection', args=[self.collection.id]), {
            'title': 'Hacked Collection',
            'description': 'Hacked Description'
        })
        self.assertEqual(response.status_code, 302)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.title, 'Test Collection')

    def test_guest_cannot_edit_collection(self):
        self.client.session.flush()
        response = self.client.post(reverse('edit_collection', args=[self.collection.id]), {
            'title': 'Hacked Collection',
            'description': 'Hacked Description'
        })
        self.assertEqual(response.status_code, 302)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.title, 'Test Collection')

    def test_librarian_can_delete_collection(self):
        self.client.login(username='librarian', password='librarianpass')
        response = self.client.post(reverse('delete_collection', args=[self.collection.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Collection.objects.filter(id=self.collection.id).exists())

    def test_patron_cannot_delete_collection(self):
        self.client.login(username='patron', password='patronpass')
        response = self.client.post(reverse('delete_collection', args=[self.collection.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Collection.objects.filter(id=self.collection.id).exists())

    def test_guest_cannot_delete_collection(self):
        self.client.session.flush()
        response = self.client.post(reverse('delete_collection', args=[self.collection.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Collection.objects.filter(id=self.collection.id).exists())

    def test_librarian_can_move_item_to_collection(self):
        self.client.login(username='librarian', password='librarianpass')
        response = self.client.post(reverse('move_item_to_collection', args=[self.item.id]), {
            'collection_id': self.collection.id
        })
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertTrue(self.item.collections.filter(id=self.collection.id).exists())

    def test_guest_cannot_move_item_to_collection(self):
        self.client.session.flush()
        response = self.client.post(reverse('move_item_to_collection', args=[self.item.id]), {
            'collection_id': self.collection.id
        })
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertFalse(self.item.collections.filter(id=self.collection.id).exists())

    def test_patron_can_add_comment(self):
        self.client.login(username='patron', password='patronpass')
        response = self.client.post(reverse('add_comment', args=[self.item.id]), {
            'text': 'New Comment',
            'rating': 5
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Comment.objects.filter(text='New Comment', item=self.item).exists())

    def test_librarian_cannot_add_comment(self):
        self.client.login(username='librarian', password='librarianpass')
        response = self.client.post(reverse('add_comment', args=[self.item.id]), {
            'text': 'Librarian Comment',
            'rating': 5
        })
        self.assertEqual(response.status_code, 302)  # should be forbidden or redirected
        self.assertFalse(Comment.objects.filter(text='Librarian Comment', item=self.item).exists())
    
    def test_guest_cannot_add_comment(self):
        self.client.session.flush()
        response = self.client.post(reverse('add_comment', args=[self.item.id]), {
            'text': 'Guest Comment',
            'rating': 5
        })
        self.assertEqual(response.status_code, 302)  # should be forbidden or redirected
        self.assertFalse(Comment.objects.filter(text='Guest Comment', item=self.item).exists())

    def test_patron_can_edit_own_comment(self):
        self.client.login(username='patron', password='patronpass')
        response = self.client.post(reverse('edit_comment', args=[self.comment.id]), {
            'text': 'Updated Comment',
            'rating': 3
        })
        self.assertEqual(response.status_code, 302)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.text, 'Updated Comment')

    def test_random_patron_cannot_edit_own_comment(self):
        self.client.login(username='patron', password='patronpass')
        self.client.session.flush()
        self.client.login(username='malicious_patron', password='password')
        response = self.client.post(reverse('edit_comment', args=[self.comment.id]), {
            'text': 'Updated Comment',
            'rating': 3
        })
        self.assertEqual(response.status_code, 302)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.text, 'This is a comment.')

    def test_librarian_cannot_edit_other_users_comment(self):
        self.client.login(username='librarian', password='librarianpass') 
        response = self.client.post(reverse('edit_comment', args=[self.comment.id]), {
            'text': 'Librarian Edited Comment',
            'rating': 1
        })
        self.assertEqual(response.status_code, 302)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.text, 'This is a comment.')

    def test_guest_cannot_edit_other_users_comment(self):
        self.client.session.flush()
        response = self.client.post(reverse('edit_comment', args=[self.comment.id]), {
            'text': 'Guest Edited Comment',
            'rating': 1
        })
        self.assertEqual(response.status_code, 302)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.text, 'This is a comment.')

    def test_patron_can_delete_own_comment(self):
        self.client.login(username='patron', password='patronpass')
        response = self.client.post(reverse('delete_comment', args=[self.comment.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Comment.objects.filter(id=self.comment.id).exists())

    def test_librarian_can_delete_any_comment(self):
        self.client.login(username='librarian', password='librarianpass')
        response = self.client.post(reverse('delete_comment', args=[self.comment.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Comment.objects.filter(id=self.comment.id).exists())
    
    def test_guest_cannot_delete_any_comment(self):
        self.client.session.flush()
        response = self.client.post(reverse('delete_comment', args=[self.comment.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Comment.objects.filter(id=self.comment.id).exists())

    def test_browse_equipment(self):
        self.client.login(username='patron', password='patronpass')
        response = self.client.get(reverse('browse_equipment'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.title)

    def test_guest_can_browse_public_equipment(self):
        self.client.logout()
        response = self.client.get(reverse('browse_equipment'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.title)
