import django.db.models.deletion
from django.db import migrations, models


def make_kinds(apps, schema_editor):
    """The two kinds the site shipped with become the first configurable rows."""
    InstitutionKind = apps.get_model("catalog", "InstitutionKind")
    for order, (slug, name, plural) in enumerate([("school", "School", "Schools"),
                                                  ("college", "College", "Colleges")]):
        InstitutionKind.objects.get_or_create(slug=slug, defaults={"name": name, "plural": plural,
                                                                   "sort_order": order})


def copy_kinds(apps, schema_editor):
    Institution = apps.get_model("catalog", "Institution")
    InstitutionKind = apps.get_model("catalog", "InstitutionKind")
    kinds = {kind.slug: kind for kind in InstitutionKind.objects.all()}
    for slug, kind in kinds.items():
        Institution.objects.filter(kind=slug).update(kind_ref=kind)
    Institution.objects.filter(kind_ref=None).update(kind_ref=kinds["school"])

    # update() skips the save signals that invalidate the public API cache.
    from apps.core.cache import bump
    bump()


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='InstitutionKind',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(help_text='Short id used in filters, e.g. school.', unique=True)),
                ('name', models.CharField(help_text='Singular, e.g. "School".', max_length=60)),
                ('plural', models.CharField(help_text='Filter chip on the events page, e.g. "Schools".',
                                            max_length=60)),
                ('sort_order', models.PositiveIntegerField(default=0, verbose_name='order')),
            ],
            options={
                'verbose_name': 'institution type',
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.RunPython(make_kinds, migrations.RunPython.noop),
        migrations.AddField(
            model_name='institution',
            name='kind_ref',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='institutions', to='catalog.institutionkind',
                                    verbose_name='type'),
        ),
        migrations.RunPython(copy_kinds, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='institution',
            name='kind',
        ),
        migrations.RenameField(
            model_name='institution',
            old_name='kind_ref',
            new_name='kind',
        ),
        migrations.AlterField(
            model_name='institution',
            name='kind',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='institutions',
                                    to='catalog.institutionkind', verbose_name='type'),
        ),
    ]
