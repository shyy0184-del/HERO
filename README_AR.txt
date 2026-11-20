HERO — نسخة Webhook للتجربة على Render Free

هذه النسخة تستخدم Web Service + Telegram Webhook بدلاً من Background Worker/Polling.

طريقة النشر:
1) ارفع مجلد الملفات إلى مستودع GitHub مجاني.
2) في Render اختر New + ثم Web Service واربط مستودع GitHub.
3) Runtime: Python
4) Build Command: pip install -r requirements.txt
5) Start Command: uvicorn bot:api --host 0.0.0.0 --port $PORT
6) أضف Environment Variables:
   BOT_TOKEN = توكن البوت
   SUPABASE_URL = رابط مشروع Supabase (Project URL)
   SUPABASE_SERVICE_ROLE_KEY = السر الخاص من Supabase Secret keys
   DEVELOPER_ID = 1806855789
   WEBHOOK_SECRET = قيمة سرية عشوائية طويلة (يمكن ترك Render يولدها)

لا تضع التوكن أو service role key داخل الملفات أو ترسلهما بالمحادثة.

مهم جداً:
- Render Free Web Services قد تدخل وضع السكون بعد عدم النشاط، وقد يتأخر وصول أول تحديث بعد الاستيقاظ. لذلك هذا حل مجاني للتجربة وليس ضمان تشغيل دائم.
- تأكد أن Supabase URL وSecret Key محفوظان في Render Environment فقط.
- هذه نسخة MVP؛ بعض وظائف AIZEL والألعاب المتقدمة ولوحة الإدارة غير منفذة بعد.
- بيانات الرتب والمجموعات والإنذارات تستخدم Supabase REST.
- اجعل HERO مشرفاً في المجموعة مع صلاحية حذف الرسائل لتعمل حماية الروابط.
