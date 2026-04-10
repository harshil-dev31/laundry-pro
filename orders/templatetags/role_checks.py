from django import template

register = template.Library()

@register.filter(name='has_group')
def has_group(user, group_name):
    # Logic: Checks if the user is in the group name you pass
    return user.groups.filter(name=group_name).exists()