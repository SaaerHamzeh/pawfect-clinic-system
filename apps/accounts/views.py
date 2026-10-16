from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from .models import User
from .forms import (
    UserCreateForm,
    UserEditForm,
    AdminPasswordResetForm,
    OfflineForgotPasswordForm,
    CUSTOM_PERMISSIONS,
    PERMISSION_CATEGORIES,
)
from .permissions import admin_required
from .services import (
    SESSION_RECOVERY_CODE_KEY,
    is_recovery_configured,
    issue_new_recovery_code,
    verify_recovery_code,
)
from apps.audit.models import AuditLog
from apps.core.utils import get_client_ip


def login_view(request):
    """Handles user login with offline validation and audit logging."""
    if request.user.is_authenticated:
        return redirect("core:dashboard")

    error_message = None

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            # Record Login in AuditLog
            AuditLog.log(
                user=user,
                action=AuditLog.Action.LOGIN,
                entity_type="جلسة مستخدم (User Session)",
                entity_id=str(user.pk),
                description=f"تسجيل دخول ناجح للمستخدم {user.username} ({user.get_role_display()})",
                ip_address=get_client_ip(request),
            )

            if user.is_admin_user and not is_recovery_configured():
                request.session[SESSION_RECOVERY_CODE_KEY] = issue_new_recovery_code()
                return redirect("accounts:recovery_code")

            next_url = request.GET.get("next") or "core:dashboard"
            return redirect(next_url)
        else:
            error_message = "اسم المستخدم أو كلمة المرور غير صحيحة. يرجى التحقق وإعادة المحاولة."
    else:
        form = AuthenticationForm()

    return render(
        request,
        "accounts/login.html",
        {
            "form": form,
            "error_message": error_message,
            "reset_form": OfflineForgotPasswordForm(),
            "show_reset": False,
        },
    )


@require_http_methods(["GET", "POST"])
def password_reset_view(request):
    """Offline password reset from the login page using the clinic recovery code."""
    if request.user.is_authenticated:
        return redirect("core:dashboard")

    error_message = None
    success_message = None
    form = OfflineForgotPasswordForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            username = form.cleaned_data["username"].strip()
            recovery_ok, recovery_error = verify_recovery_code(form.cleaned_data["recovery_code"])
            target_user = User.objects.filter(username__iexact=username, is_active=True).first()

            if recovery_ok and target_user:
                target_user.set_password(form.cleaned_data["new_password"])
                target_user.save(update_fields=["password"])
                AuditLog.log(
                    user=target_user,
                    action=AuditLog.Action.UPDATE,
                    entity_type="حساب مستخدم (User Account)",
                    entity_id=str(target_user.pk),
                    description=f"إعادة تعيين كلمة المرور للمستخدم «{target_user.username}» عبر رمز الاستعادة من صفحة الدخول",
                    ip_address=get_client_ip(request),
                )
                success_message = "تم تعيين كلمة المرور الجديدة بنجاح. يمكنك تسجيل الدخول الآن."
                form = OfflineForgotPasswordForm()
            else:
                error_message = recovery_error if not recovery_ok else "اسم المستخدم أو رمز الاستعادة غير صحيح."
        else:
            error_message = " ".join([err[0] for err in form.errors.values()])

    return render(
        request,
        "accounts/login.html",
        {
            "form": AuthenticationForm(),
            "reset_form": form,
            "error_message": error_message,
            "success_message": success_message,
            "show_reset": True,
        },
    )


@admin_required
def recovery_code_view(request):
    """One-time display of a newly generated recovery code."""
    code = request.session.get(SESSION_RECOVERY_CODE_KEY)
    if request.method == "POST":
        request.session.pop(SESSION_RECOVERY_CODE_KEY, None)
        return redirect("core:dashboard")
    if not code:
        return redirect("settings:users")
    return render(request, "accounts/recovery_code.html", {"recovery_code": code})


@admin_required
@require_POST
def regenerate_recovery_code(request):
    """Admin regenerates the clinic password recovery code."""
    code = issue_new_recovery_code()
    request.session[SESSION_RECOVERY_CODE_KEY] = code
    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.UPDATE,
        entity_type="رمز استعادة كلمة المرور",
        entity_id="1",
        description="إعادة توليد رمز استعادة كلمة المرور للعيادة",
        ip_address=get_client_ip(request),
    )
    return redirect("accounts:recovery_code")


@require_http_methods(["GET", "POST"])
def logout_view(request):
    """Handles user logout and audit logging."""
    if request.user.is_authenticated:
        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.LOGOUT,
            entity_type="جلسة مستخدم (User Session)",
            entity_id=str(request.user.pk),
            description=f"تسجيل خروج للمستخدم {request.user.username}",
            ip_address=get_client_ip(request),
        )
        logout(request)
    return redirect("accounts:login")


# --- ADMIN USER MANAGEMENT VIEWS ---

@admin_required
def user_list(request):
    """Admin view to list all staff and vet users with their granular permissions."""
    role = request.GET.get("role", "all")
    status_filter = request.GET.get("status", "all")
    q = request.GET.get("q", "").strip()

    users_qs = User.objects.all().prefetch_related("user_permissions")

    if role and role != "all":
        users_qs = users_qs.filter(role=role.upper())

    if status_filter == "active":
        users_qs = users_qs.filter(is_active=True)
    elif status_filter == "inactive":
        users_qs = users_qs.filter(is_active=False)

    if q:
        users_qs = users_qs.filter(
            Q(username__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(email__icontains=q)
        )

    users_qs = users_qs.order_by("-is_superuser", "role", "username")

    # Stats
    total_users_count = User.objects.count()
    vets_count = User.objects.filter(role=User.Role.VET).count()
    staff_count = User.objects.filter(role=User.Role.STAFF).count()
    active_count = User.objects.filter(is_active=True).count()

    # Pagination
    paginator = Paginator(users_qs, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    form = UserCreateForm()

    context = {
        "users_list": page_obj,
        "page_obj": page_obj,
        "total_users_count": total_users_count,
        "vets_count": vets_count,
        "staff_count": staff_count,
        "active_count": active_count,
        "form": form,
        "add_form": form,
        "role": role,
        "status_filter": status_filter,
        "q": q,
        "available_permissions": CUSTOM_PERMISSIONS,
        "permission_categories": PERMISSION_CATEGORIES,
    }
    return render(request, "users/users.html", context)


@admin_required
@require_POST
def user_create(request):
    """Admin view to create a new user and assign granular permissions."""
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    form = UserCreateForm(request.POST)
    if form.is_valid():
        new_user = form.save()

        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.CREATE,
            entity_type="حساب مستخدم (User Account)",
            entity_id=str(new_user.pk),
            description=(
                f"إنشاء حساب مستخدم جديد «{new_user.username}» "
                f"بدور ({new_user.get_role_display()})"
            ),
            ip_address=get_client_ip(request),
        )

        msg = f"تم إنشاء حساب المستخدم «{new_user.username}» بنجاح وتعيين صلاحياته."
        messages.success(request, msg)
        redirect_url = reverse("settings:users")
        if is_ajax:
            return JsonResponse({"success": True, "redirect_url": redirect_url, "message": msg})
    else:
        error_list = [err for sublist in form.errors.values() for err in sublist]
        error_msg = "تعذر إنشاء المستخدم: " + "; ".join(error_list) if error_list else "يرجى التحقق من صحة البيانات المدخلة."
        if is_ajax:
            return JsonResponse({
                "success": False,
                "error": error_msg,
                "field_errors": {k: [str(e) for e in v] for k, v in form.errors.items()}
            }, status=400)
        messages.error(request, error_msg)

    return redirect("settings:users")


@admin_required
@require_POST
def user_update(request, user_id):
    """Admin view to update user details and granted permissions."""
    target_user = get_object_or_404(User, pk=user_id)
    previous_username = target_user.username
    form = UserEditForm(request.POST, instance=target_user)
    if form.is_valid():
        updated_user = form.save()

        audit_description = f"تحديث بيانات وصلاحيات المستخدم «{updated_user.username}»"
        if previous_username != updated_user.username:
            audit_description += f" — تغيير اسم الدخول من «{previous_username}» إلى «{updated_user.username}»"

        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.UPDATE,
            entity_type="حساب مستخدم (User Account)",
            entity_id=str(updated_user.pk),
            description=audit_description,
            ip_address=get_client_ip(request),
        )

        messages.success(request, f"تم تحديث صلاحيات وبيانات المستخدم «{updated_user.username}» بنجاح.")
    else:
        error_msg = "تعذر تحديث المستخدم: " + "; ".join(
            [f"{err[0]}" for err in form.errors.values()]
        )
        messages.error(request, error_msg)

    return redirect("settings:users")


@admin_required
@require_POST
def user_toggle_status(request, user_id):
    """Admin view to enable or disable a user account."""
    target_user = get_object_or_404(User, pk=user_id)

    if target_user == request.user:
        messages.error(request, "لا يمكنك تعطيل حسابك الشخصي الحالي.")
        return redirect("settings:users")

    if target_user.role == User.Role.ADMIN and target_user.is_active:
        remaining_admins = User.objects.filter(role=User.Role.ADMIN, is_active=True).exclude(pk=target_user.pk).count()
        if remaining_admins == 0:
            messages.error(request, "لا يمكن تعطيل حساب المدير النشط الوحيد في النظام للحفاظ على صلاحيات الإدارة.")
            return redirect("settings:users")

    target_user.is_active = not target_user.is_active
    target_user.save(update_fields=["is_active"])

    status_str = "تفعيل" if target_user.is_active else "تعطيل"

    AuditLog.log(
        user=request.user,
        action=AuditLog.Action.UPDATE,
        entity_type="حساب مستخدم (User Account)",
        entity_id=str(target_user.pk),
        description=f"{status_str} حساب المستخدم «{target_user.username}»",
        ip_address=get_client_ip(request),
    )

    messages.success(request, f"تم {status_str} حساب المستخدم «{target_user.username}» بنجاح.")
    return redirect("settings:users")


@admin_required
@require_POST
def user_reset_password(request, user_id):
    """Admin view to reset a user's password."""
    target_user = get_object_or_404(User, pk=user_id)
    form = AdminPasswordResetForm(request.POST)
    if form.is_valid():
        new_password = form.cleaned_data["new_password"]
        target_user.set_password(new_password)
        target_user.save(update_fields=["password"])

        AuditLog.log(
            user=request.user,
            action=AuditLog.Action.UPDATE,
            entity_type="حساب مستخدم (User Account)",
            entity_id=str(target_user.pk),
            description=f"إعادة تعيين كلمة المرور للمستخدم «{target_user.username}» بواسطة المدير",
            ip_address=get_client_ip(request),
        )

        messages.success(request, f"تمت إعادة تعيين كلمة المرور للمستخدم «{target_user.username}» بنجاح.")
    else:
        error_msg = "تعذر تعيين كلمة المرور: " + "; ".join(
            [f"{err[0]}" for err in form.errors.values()]
        )
        messages.error(request, error_msg)

    return redirect("settings:users")
