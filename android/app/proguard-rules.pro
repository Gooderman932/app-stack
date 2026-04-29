# Keep TWA / androidbrowserhelper classes
-keep class com.google.androidbrowserhelper.** { *; }
-keep class androidx.browser.trusted.** { *; }

# Keep Play Billing Library
-keep class com.android.billingclient.** { *; }

# Keep Kotlin coroutines (used by billing-ktx)
-keepnames class kotlinx.coroutines.internal.MainDispatcherFactory {}
-keepnames class kotlinx.coroutines.CoroutineExceptionHandler {}
