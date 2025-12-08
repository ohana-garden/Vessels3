/**
 * Ohana Garden Website - Main JavaScript
 * Handles interactivity, animations, and navigation
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all modules
    initMobileMenu();
    initSmoothScroll();
    initNavbarScroll();
    initScrollAnimations();
    initParallax();
});

/**
 * Mobile Menu Toggle
 */
function initMobileMenu() {
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const navLinks = document.querySelector('.nav-links');

    if (mobileMenuBtn && navLinks) {
        mobileMenuBtn.addEventListener('click', function() {
            navLinks.classList.toggle('active');
            mobileMenuBtn.classList.toggle('active');

            // Animate hamburger to X
            const spans = mobileMenuBtn.querySelectorAll('span');
            if (mobileMenuBtn.classList.contains('active')) {
                spans[0].style.transform = 'rotate(45deg) translate(5px, 5px)';
                spans[1].style.opacity = '0';
                spans[2].style.transform = 'rotate(-45deg) translate(5px, -5px)';
            } else {
                spans[0].style.transform = 'none';
                spans[1].style.opacity = '1';
                spans[2].style.transform = 'none';
            }
        });

        // Close menu when clicking on a link
        navLinks.querySelectorAll('a').forEach(function(link) {
            link.addEventListener('click', function() {
                navLinks.classList.remove('active');
                mobileMenuBtn.classList.remove('active');
                const spans = mobileMenuBtn.querySelectorAll('span');
                spans[0].style.transform = 'none';
                spans[1].style.opacity = '1';
                spans[2].style.transform = 'none';
            });
        });
    }
}

/**
 * Smooth Scroll for Anchor Links
 */
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(function(anchor) {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');

            if (targetId === '#') return;

            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                const navHeight = document.querySelector('.navbar').offsetHeight;
                const targetPosition = targetElement.getBoundingClientRect().top + window.pageYOffset - navHeight;

                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });
}

/**
 * Navbar Background Change on Scroll
 */
function initNavbarScroll() {
    const navbar = document.querySelector('.navbar');

    if (navbar) {
        let lastScrollTop = 0;

        window.addEventListener('scroll', function() {
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;

            // Add/remove scrolled class for background change
            if (scrollTop > 50) {
                navbar.classList.add('scrolled');
                navbar.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.1)';
            } else {
                navbar.classList.remove('scrolled');
                navbar.style.boxShadow = '0 1px 3px rgba(0, 0, 0, 0.08)';
            }

            lastScrollTop = scrollTop;
        });
    }
}

/**
 * Scroll-Triggered Animations
 */
function initScrollAnimations() {
    // Elements to animate on scroll
    const animatedElements = document.querySelectorAll(
        '.value-card, .stat-card, .feature-card, .vessel-feature, .tech-layer, .tech-detail'
    );

    // Intersection Observer options
    const observerOptions = {
        root: null,
        rootMargin: '0px',
        threshold: 0.1
    };

    // Create observer
    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-in');
                // Optional: unobserve after animation
                // observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Add initial styles and observe elements
    animatedElements.forEach(function(element, index) {
        element.style.opacity = '0';
        element.style.transform = 'translateY(30px)';
        element.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        element.style.transitionDelay = (index % 4) * 0.1 + 's';
        observer.observe(element);
    });

    // CSS class for animation
    const style = document.createElement('style');
    style.textContent = `
        .animate-in {
            opacity: 1 !important;
            transform: translateY(0) !important;
        }
    `;
    document.head.appendChild(style);
}

/**
 * Parallax Effect for Hero Section
 */
function initParallax() {
    const hero = document.querySelector('.hero');
    const floatingElements = document.querySelectorAll('.float-item');

    if (hero && floatingElements.length > 0) {
        window.addEventListener('scroll', function() {
            const scrollTop = window.pageYOffset;
            const heroHeight = hero.offsetHeight;

            if (scrollTop < heroHeight) {
                floatingElements.forEach(function(element, index) {
                    const speed = 0.2 + (index * 0.1);
                    const yPos = scrollTop * speed;
                    element.style.transform = `translateY(${yPos}px)`;
                });
            }
        });
    }
}

/**
 * Utility: Debounce Function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction() {
        const context = this;
        const args = arguments;
        const later = function() {
            timeout = null;
            func.apply(context, args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Active Section Highlighting in Navigation
 */
(function() {
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-links a[href^="#"]');

    if (sections.length > 0 && navLinks.length > 0) {
        const observerOptions = {
            root: null,
            rootMargin: '-50% 0px -50% 0px',
            threshold: 0
        };

        const observer = new IntersectionObserver(function(entries) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    const id = entry.target.getAttribute('id');

                    navLinks.forEach(function(link) {
                        link.classList.remove('active');
                        if (link.getAttribute('href') === '#' + id) {
                            link.classList.add('active');
                        }
                    });
                }
            });
        }, observerOptions);

        sections.forEach(function(section) {
            observer.observe(section);
        });

        // Add active styling
        const style = document.createElement('style');
        style.textContent = `
            .nav-links a.active {
                color: var(--color-ocean-deep);
            }
            .nav-links a.active::after {
                width: 100%;
            }
        `;
        document.head.appendChild(style);
    }
})();

/**
 * Console Welcome Message
 */
console.log('%c🌺 Ohana Garden', 'font-size: 24px; font-weight: bold; color: #2d5a3d;');
console.log('%cBuilt with aloha, powered by Vessels AI', 'font-size: 14px; color: #4a9aaa;');
console.log('%cLearn more: https://github.com/ohana-garden/vessels3', 'font-size: 12px; color: #6a6a6a;');
