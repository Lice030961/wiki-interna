from django.db import models
from django.utils.text import slugify


class MajorTopic(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=10, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'title']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class MinorTopic(models.Model):
    major_topic = models.ForeignKey(MajorTopic, on_delete=models.CASCADE, related_name='minor_topics')
    title = models.CharField(max_length=200)
    slug = models.SlugField(blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=10, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'title']
        unique_together = ['major_topic', 'slug']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.major_topic.title} → {self.title}'


class ContentBlock(models.Model):
    TEXT = 'text'
    IMAGE = 'image'
    VIDEO = 'video'
    CHECKLIST = 'checklist'
    BLOCK_TYPES = [
        (TEXT, 'Texto'),
        (IMAGE, 'Imagem'),
        (VIDEO, 'Vídeo'),
        (CHECKLIST, 'Checklist'),
    ]

    minor_topic = models.ForeignKey(MinorTopic, on_delete=models.CASCADE, related_name='blocks')
    block_type = models.CharField(max_length=20, choices=BLOCK_TYPES, default=TEXT)
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField(blank=True)
    file = models.FileField(upload_to='uploads/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.minor_topic.title} – {self.block_type} #{self.order}'
