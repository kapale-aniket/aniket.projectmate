from django import forms


class NaukriApplyForm(forms.Form):
    job_keyword = forms.CharField(
        required=False,
        initial="python",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "python"}),
    )
    multi_apply_batch_size = forms.IntegerField(
        required=False,
        initial=5,
        min_value=1,
        max_value=20,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    headless = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
