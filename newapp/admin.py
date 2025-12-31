from django.contrib import admin
from .models import Admin, User, Message, ChatGPTPrompt, ExternalAPI

@admin.register(ExternalAPI)
class ExternalAPIAdmin(admin.ModelAdmin):
    actions = ['test_api_connection']

    def test_api_connection(self, request, queryset):
        import requests
        success_count = 0
        fail_count = 0
        for tool in queryset:
            try:
                # Simple Ping - logic.execute_tool requires args, so we prefer a simple ping here
                # We send an empty payload (or raw payload with {{}} intact) to check connectivity
                # Most APIs will return 400 or 200, either implies connection worked.
                
                # Check method
                if tool.method.upper() == 'GET':
                    resp = requests.get(tool.url, headers=tool.headers, timeout=5)
                else:
                    # For POST, send empty JSON or the raw template
                    resp = requests.post(tool.url, headers=tool.headers, json=tool.payload, timeout=5)
                
                self.message_user(request, f"[{tool.name}] HTTP {resp.status_code}: {resp.text[:100]}...", level='info')
                success_count += 1
            except Exception as e:
                self.message_user(request, f"[{tool.name}] FAILED: {str(e)}", level='error')
                fail_count += 1
        
        self.message_user(request, f"Test Complete: {success_count} reachable, {fail_count} failed.")

    test_api_connection.short_description = "Test Connection (Ping) for selected APIs"

    list_display = ('name', 'url', 'method', 'test_status_column')
    list_filter = ('admin', 'method')
    search_fields = ('name', 'description', 'url')
    
    def test_status_column(self, obj):
        return f"{obj.method} -> {obj.url[:30]}..."

    fieldsets = (
        ('Tool Configuration', {
            'fields': ('admin', 'name', 'description')
        }),
        ('API Details', {
            'fields': ('url', 'method', 'headers', 'payload')
        }),
    )

@admin.register(Admin)
class AdminModel(admin.ModelAdmin):
    list_display = ('id', 'whatsapp_phone_id', 'chatgpt_mode')

@admin.register(ChatGPTPrompt)
class ChatGPTPromptAdmin(admin.ModelAdmin):
    list_display = ('id', 'updated_at')

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('phone_no', 'name', 'admin_id')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'who', 'messages', 'created_at')
