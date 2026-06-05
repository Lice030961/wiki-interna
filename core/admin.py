from django.contrib import admin
from .models import MajorTopic, MinorTopic, ContentBlock


@admin.register(MajorTopic)
class MajorTopicAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'order')
    search_fields = ('title',)


@admin.register(MinorTopic)
class MinorTopicAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'major_topic', 'order')
    list_filter = ('major_topic',)
    search_fields = ('title',)


@admin.register(ContentBlock)
class ContentBlockAdmin(admin.ModelAdmin):
    list_display = ('minor_topic', 'block_type', 'title', 'order')
    list_filter = ('block_type', 'minor_topic__major_topic')

    class Media:
        js = ('js/admin_content_block.js',)
