from django import forms

from .models import Comment
        
from allauth.account.forms import SignupForm

from .models import Post
import uuid
from django.utils.text import slugify

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        exclude = ["post"]
        labels = {
          "user_name": "Your Name",
          "user_email": "Your Email",
          "text": "Your Comment"
        }


class CustomSignupForm(SignupForm):
    first_name = forms.CharField(max_length=30, label="First name")
    last_name = forms.CharField(max_length=30, label="Last name")

    def save(self, request):
        user = super().save(request)

        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]

        # 🔥 IMPORTANT : générer un username UNIQUE
        if not user.username:
            base = slugify(user.first_name) or "user"
            user.username = f"{base}-{uuid.uuid4().hex[:8]}"

        user.save()
        return user
# blog/forms.py

from allauth.account.adapter import DefaultAccountAdapter




class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["title", "excerpt", "image", "content", "is_public"]
        exclude = ("slug", "owner", "date")