(function() {

  // Load the GA4 script asynchronously
  const script = document.createElement('script');
  script.async = true;
  script.src = 'https://www.googletagmanager.com/gtag/js?id=G-7NFDYRTDDT';
  document.head.appendChild(script);

  // Initialize the dataLayer
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}

  // Set up GA4 with privacy-first configurations
  gtag('js', new Date());

  // Configure Google Analytics with privacy-first options
  gtag('config', 'G-7NFDYRTDDT', {
      'anonymize_ip': true,           // Anonymize IP addresses
      'allow_google_signals': false, // Disable Google Signals
      'storage': 'none',             // Disable cookies
      'cookie_flags': 'SameSite=None;Secure' // Prevent cookies if used inadvertently
  });

  // Use Consent Mode to limit data collection
  gtag('consent', 'default', {
      'ad_storage': 'denied',
      'analytics_storage': 'denied'
  });

  // // Optional: Additional configurations for enhanced privacy
  // console.log('GA4 configured with privacy-first settings');
})();
