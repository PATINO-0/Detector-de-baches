-- Crea primero el bucket privado «modelos» desde Storage en Supabase.
begin;

do $$
begin
    if not exists (
        select 1 from storage.buckets where id = 'modelos' and public = false
    ) then
        raise exception 'Crea primero el bucket privado modelos desde Storage.';
    end if;
end;
$$;

drop policy if exists "roadvision_descarga_modelos_anon" on storage.objects;

-- La clave pública solo necesita descargar estos dos objetos por su ruta exacta.
create policy "roadvision_descarga_modelos_anon"
on storage.objects
for select
to anon
using (
    bucket_id = 'modelos'
    and name in ('baches.onnx', 'grietas.onnx')
    and storage.allow_only_operation('object.get_authenticated')
);

commit;
